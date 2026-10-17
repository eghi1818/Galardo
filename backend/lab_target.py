"""GALARDO - Lab-only target service with a REAL capacity ceiling.

Technical Design 1.1 (Target). Binds 127.0.0.1 only.

WHY v2 EXISTS
-------------
v1 used ThreadingHTTPServer: one thread per connection, NO cap, and
/api/heavy only *sleeps* (zero CPU). Result: 300 VUs -> 300 idle threads ->
zero queueing -> an out-of-band probe can never fail -> GOAL 2 unprovable.

v2 adds the missing ingredient: a CEILING.
  * CapacityGate - fixed worker pool + bounded backlog, exactly like
    nginx worker_processes / gunicorn --workers / php-fpm pm.max_children.
    Requests past the pool wait in a backlog; past the backlog they are
    SHED with 503 (realistic overload signature).
  * /api/cpu     - real CPU burn (busy loop, not sleep) for genuine
    resource exhaustion instead of simulated latency.
  * /control/*   - ALWAYS bypasses the gate, so capacity stays changeable
    even while the target is collapsed.

Backwards compatible: /healthz, /api/slow, /api/error, /api/heavy,
/control/mode, /control/degrade, /control/recover all keep working.
"""
import os
import argparse
import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

GATED_PATHS = ("/", "/healthz", "/api/slow", "/api/error", "/api/heavy", "/api/cpu")

STATE = {
    "mode": "healthy",
    "slow_ms": 20,
    "error_rate": 0.0,
    "heavy_ms": 150,
    "cpu_burn_ms": 0,
}
LOCK = threading.Lock()
STARTED_AT = time.time()


# ---------------------------------------------------------------------------
# THE CEILING
# ---------------------------------------------------------------------------
class CapacityGate:
    """Simulated fixed worker pool + bounded backlog.

    workers == 0 -> unlimited (v1 behaviour, kept for comparison runs).
    backlog == 0 -> unbounded waiting queue (no shedding).
    """

    def __init__(self, workers=0, backlog=0):
        self._cv = threading.Condition()
        self.workers = max(0, int(workers))
        self.backlog = max(0, int(backlog))
        self.inflight = 0
        self.waiting = 0
        self.peak_inflight = 0
        self.peak_waiting = 0
        self.served = 0
        self.shed = 0
        self.wait_ms_total = 0.0

    def configure(self, workers=None, backlog=None):
        with self._cv:
            if workers is not None:
                self.workers = max(0, int(workers))
            if backlog is not None:
                self.backlog = max(0, int(backlog))
            self._cv.notify_all()
        return self.stats()

    def acquire(self):
        """(admitted, waited_ms). admitted=False -> shed with 503."""
        t0 = time.time()
        with self._cv:
            if self.workers > 0 and self.inflight >= self.workers:
                if self.backlog > 0 and self.waiting >= self.backlog:
                    self.shed += 1
                    return False, (time.time() - t0) * 1000.0
                self.waiting += 1
                if self.waiting > self.peak_waiting:
                    self.peak_waiting = self.waiting
                while self.workers > 0 and self.inflight >= self.workers:
                    self._cv.wait()
                self.waiting -= 1
            self.inflight += 1
            if self.inflight > self.peak_inflight:
                self.peak_inflight = self.inflight
            waited = (time.time() - t0) * 1000.0
            self.wait_ms_total += waited
            return True, waited

    def release(self):
        with self._cv:
            if self.inflight > 0:
                self.inflight -= 1
            self.served += 1
            self._cv.notify()

    def stats(self):
        with self._cv:
            return {
                "workers": self.workers,
                "backlog": self.backlog,
                "inflight": self.inflight,
                "waiting": self.waiting,
                "peak_inflight": self.peak_inflight,
                "peak_waiting": self.peak_waiting,
                "served": self.served,
                "shed_503": self.shed,
                "avg_wait_ms": round(self.wait_ms_total / self.served, 2) if self.served else 0.0,
                "saturated": bool(self.peak_waiting > 0 or self.shed > 0),
            }


GATE = CapacityGate()


def _burn(ms):
    """Busy loop = real CPU consumption (unlike time.sleep)."""
    if ms <= 0:
        return
    end = time.time() + (ms / 1000.0)
    x = 0
    while time.time() < end:
        x += 1


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
class TargetHandler(BaseHTTPRequestHandler):
    server_version = "GalardoLabTarget/2.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        self._serve("GET")

    def do_HEAD(self):
        self._serve("HEAD")

    def do_POST(self):
        self._serve("POST")

    def _json(self, code, obj, extra=None, reason=None):
        body = json.dumps(obj).encode()
        self.send_response(code, reason)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _serve(self, method):
        path, _, query = self.path.partition("?")
        q = parse_qs(query or "")

        # /control/* ALWAYS bypasses the gate: capacity stays changeable under collapse
        if path.startswith("/control/"):
            return self._control(path, q)

        admitted, waited = GATE.acquire()
        if not admitted:
            return self._json(503, {"error": "pool_full",
                                    "hint": "worker pool + backlog saturated",
                                    "workers": GATE.workers, "backlog": GATE.backlog},
                              {"Retry-After": "1", "X-Galardo-Shed": "1"},
                              reason="Service Unavailable")
        try:
            return self._app(path, q, waited)
        finally:
            GATE.release()

    def _app(self, path, q, waited):
        with LOCK:
            mode = STATE["mode"]
            slow_ms = STATE["slow_ms"]
            error_rate = STATE["error_rate"]
            heavy_ms = STATE["heavy_ms"]
            cpu_burn_ms = STATE["cpu_burn_ms"]

        if cpu_burn_ms > 0:
            _burn(cpu_burn_ms)

        if mode == "degraded":
            time.sleep(min(slow_ms, 2500) / 1000.0)
            if random.random() < error_rate:
                return self._json(503, {"status": "degraded", "note": "synthetic fixture"})

        if path == "/healthz":
            return self._json(200, {"status": "ok", "mode": mode, "ts": time.time()})

        if path == "/api/heavy":
            time.sleep(heavy_ms / 1000.0)
            return self._json(200, {"path": path, "slept_ms": heavy_ms,
                                    "queued_ms": round(waited, 2), "ts": time.time()})

        if path == "/api/cpu":
            ms = int((q.get("ms") or [cpu_burn_ms or 50])[0])
            _burn(ms)
            return self._json(200, {"path": path, "burned_ms": ms,
                                    "queued_ms": round(waited, 2), "ts": time.time()})

        if path in ("/", "/api/slow", "/api/error"):
            return self._json(200, {"path": path, "mode": mode,
                                    "queued_ms": round(waited, 2), "ts": time.time()})

        return self._json(404, {"error": "not found",
                                "hint": "allowed: /healthz /api/slow /api/error /api/heavy /api/cpu"})

    # ------------------------------------------------------------------
    def _control(self, path, q):
        def arg(*keys, default=None):
            for k in keys:
                if k in q and q[k]:
                    return q[k][0]
            return default

        if path in ("/control/mode", "/control/stats"):
            with LOCK:
                st = dict(STATE)
            return self._json(200, {"gate": GATE.stats(), "state": st,
                                    "uptime_sec": round(time.time() - STARTED_AT, 1)})

        if path == "/control/capacity":
            w = arg("workers", "n")
            b = arg("backlog", "q")
            gate = GATE.configure(workers=None if w is None else int(w),
                                  backlog=None if b is None else int(b))
            return self._json(200, {"ok": True, "gate": gate})

        if path == "/control/heavy":
            with LOCK:
                STATE["heavy_ms"] = int(arg("ms", default=150))
                v = STATE["heavy_ms"]
            return self._json(200, {"ok": True, "heavy_ms": v})

        if path == "/control/cpu":
            with LOCK:
                STATE["cpu_burn_ms"] = int(arg("ms", default=0))
                v = STATE["cpu_burn_ms"]
            return self._json(200, {"ok": True, "cpu_burn_ms": v})

        if path == "/control/slow":
            with LOCK:
                STATE["slow_ms"] = int(arg("ms", default=20))
                v = STATE["slow_ms"]
            return self._json(200, {"ok": True, "slow_ms": v})

        if path == "/control/error":
            with LOCK:
                STATE["error_rate"] = float(arg("rate", default=0.0))
                v = STATE["error_rate"]
            return self._json(200, {"ok": True, "error_rate": v})

        if path == "/control/degrade":
            with LOCK:
                STATE.update({"mode": "degraded", "slow_ms": 2500, "error_rate": 0.6})
                st = dict(STATE)
            return self._json(200, dict(st, note="synthetic degradation ACTIVE"))

        if path == "/control/recover":
            with LOCK:
                STATE.update({"mode": "healthy", "slow_ms": 20, "error_rate": 0.0})
                st = dict(STATE)
            return self._json(200, dict(st, note="fixture restored"))

        if path == "/control/reset":
            GATE.configure(workers=0, backlog=0)
            with LOCK:
                STATE.update({"mode": "healthy", "slow_ms": 20, "error_rate": 0.0,
                              "heavy_ms": 150, "cpu_burn_ms": 0})
                st = dict(STATE)
            return self._json(200, {"ok": True, "gate": GATE.stats(), "state": st})

        return self._json(404, {"error": "unknown control path", "got": path})


def _bind_host():
    """Host bind: GALARDO_BIND (dipakai container) atau 127.0.0.1."""
    return os.environ.get("GALARDO_BIND", "127.0.0.1")


def serve(host=_bind_host(), port=8088, workers=0, backlog=0):
    GATE.configure(workers=workers, backlog=backlog)
    httpd = ThreadingHTTPServer((host, port), TargetHandler)
    httpd.daemon_threads = True
    print("[galardo-target] v2 on http://%s:%d  (/healthz, /api/*, /control/*)" % (host, port))
    print("[galardo-target] ceiling: workers=%s backlog=%s  (0 = unlimited)"
          % (workers or "unlimited", backlog or "unlimited"))
    httpd.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--backlog", type=int, default=0)
    a = ap.parse_args()
    serve(a.host, a.port, a.workers, a.backlog)
