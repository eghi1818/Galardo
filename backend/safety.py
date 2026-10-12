"""GALARDO - Independent health probe + Safety controller (Technical Design §10, §9; AI & Safety Governance §4).

Probe runs in its own thread, separate from traffic: exact URL from target's
probe contract, no redirect follow, consecutive-failure counter, states
UNKNOWN -> HEALTHY -> DEGRADED -> ABORT_REQUESTED -> RECOVERING -> RECOVERED.
Probe outage == UNKNOWN, never healthy.

SafetyController consumes probe state + telemetry freshness + policy
thresholds and issues idempotent, persisted ABORT events. UNKNOWN is unsafe.
"""
import json
import threading
import time
import urllib.error
import urllib.request

import db
from util import now_iso, now_ts

ssl_ctx = None
try:
    import ssl
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
except Exception:
    pass


class HealthProbe(threading.Thread):
    """Independent probe: does NOT follow redirects, bounded timeout."""

    def __init__(self, job_id, probe_contract, interval=2.0, timeout=1.0, failure_threshold=3):
        super().__init__(daemon=True, name=f"probe-{job_id[:12]}")
        self.job_id = job_id
        self.contract = probe_contract or {}
        self.url = self.contract.get("url", "")
        self.expected_status = int(self.contract.get("expected_status", 200))
        self.interval = interval
        self.timeout = timeout
        self.failure_threshold = failure_threshold
        self.state = "UNKNOWN"
        self.last_error = None
        self.last_checked_at = None
        self.consecutive_failures = 0
        self.last_latency_ms = None
        self.stop = threading.Event()
        self.history = []  # [(ts, state, latency_ms, err)]

    def run(self):
        while not self.stop.is_set():
            ok, latency, err = self._check()
            self.last_checked_at = now_iso()
            self.last_latency_ms = round(latency * 1000, 1) if ok else None
            if ok:
                self.consecutive_failures = 0
                self.state = "HEALTHY"
                self.last_error = None
            else:
                self.consecutive_failures += 1
                self.last_error = err
                # TD §10: DEGRADED only after N CONSECUTIVE failures. A single
                # transient blip (e.g. CF origin cold TTFB vs tight timeout)
                # must NOT flip HEALTHY -> DEGRADED (false-positive abort).
                if self.state in ("ABORT_REQUESTED",):
                    pass
                elif self.consecutive_failures >= self.failure_threshold:
                    self.state = "DEGRADED"
                # else: keep current state; failure counter exposed for UI
            self.history.append((now_iso(), self.state, self.last_latency_ms, err))
            self.history[:] = self.history[-600:]
            self.stop.wait(self.interval)

    def _check(self):
        if not self.url:
            return False, 0.0, "probe contract url missing"
        t0 = time.time()
        try:
            req = urllib.request.Request(self.url, method="GET",
                                         headers={"User-Agent": "galardo-probe/1.0"})
            opener = urllib.request.build_opener(NoRedirect)
            with opener.open(req, timeout=self.timeout) as resp:
                resp.read(2048)
                return resp.status == self.expected_status, time.time() - t0, None
        except urllib.error.HTTPError as e:
            return e.code == self.expected_status, time.time() - t0, f"http {e.code}"
        except Exception as e:
            return False, time.time() - t0, str(e)[:120]

    def snapshot(self):
        return {"state": self.state, "consecutive_failures": self.consecutive_failures,
                "last_checked_at": self.last_checked_at, "last_latency_ms": self.last_latency_ms,
                "last_error": self.last_error}

    def recovery_state(self):
        return self.state


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # never follow redirects outside allowlist


class SafetyController:
    """Evaluates probe + telemetry freshness + thresholds; issues idempotent abort.
    Signals (Governance §4): probe failures, 5xx rate, p95 breach, telemetry staleness,
    manual abort, controller health. UNKNOWN != HEALTHY."""

    def __init__(self, job_id, policy, probe, telemetry, abort_fn, on_event=None,
                 telemetry_stale_sec=6, startup_grace_sec=15):
        self.job_id = job_id
        self.policy = policy or {}
        self.probe = probe
        self.telemetry = telemetry
        self.abort_fn = abort_fn  # callable(reason_code, detail) -> bool (idempotent)
        self.on_event = on_event
        self.telemetry_stale_sec = telemetry_stale_sec
        self.startup_grace_sec = startup_grace_sec  # engine warm-up before staleness applies
        self.started_ts = time.time()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True, name=f"safety-{job_id[:12]}")
        self.decisions = []
        self.p95_limit_ms = self.policy.get("max_p95_ms")
        self.err_pct_limit = self.policy.get("max_error_pct", 10.0)
        self.abort_requested = False

    def start(self):
        self.thread.start()

    def stop_controller(self):
        self.stop.set()

    def _emit(self, severity, message, snapshot=None):
        ev = {"at": now_iso(), "severity": severity, "message": message, "snapshot": snapshot or {}}
        self.decisions.append(ev)
        self.decisions[:] = self.decisions[-200:]
        if self.on_event:
            try:
                self.on_event(severity, message, snapshot)
            except Exception:
                pass

    def _issue_abort(self, reason_code, detail):
        if self.abort_requested:
            return True
        self.abort_requested = True
        self._emit("CRIT", f"ABORT issued: [{reason_code}] {detail}")
        try:
            db.observation(self.job_id, "safety", "CRIT", f"ABORT [{reason_code}] {detail}")
        except Exception:
            pass
        return self.abort_fn(reason_code, detail)

    def evaluate_once(self):
        """One evaluation pass; returns current decision state."""
        snap = self.probe.snapshot() if self.probe else {"state": "UNKNOWN"}
        state = snap.get("state", "UNKNOWN")

        # 1. Probe state — UNKNOWN/DEGRADED is unsafe
        if state == "DEGRADED":
            self._issue_abort("PROBE_DEGRADED",
                              f"probe failures={snap.get('consecutive_failures')} last_error={snap.get('last_error')}")
        elif state == "UNKNOWN":
            self._issue_abort("PROBE_UNKNOWN", f"probe UNKNOWN last_error={snap.get('last_error')}")

        # 2. Telemetry freshness — stale stream is fail-safe.
        # Startup grace: between controller start and first request there is by
        # definition no telemetry; that is warm-up, not staleness.
        in_grace = (time.time() - self.started_ts) < self.startup_grace_sec
        agg = self.telemetry.window(5)
        if agg["requests"] == 0 and self._running_expected() and not in_grace:
            self._emit("WARN", "telemetry window empty (0 requests in 5s)")
        if not in_grace and self._running_expected():
            age = self._last_data_age()
            if age is None or age > self.telemetry_stale_sec:
                self._issue_abort("TELEMETRY_STALE",
                                  f"no telemetry for >{self.telemetry_stale_sec}s while job expected running")

        # 3. Policy thresholds from approved policy version
        if agg["requests"] >= 10:
            if self.err_pct_limit is not None and agg["error_pct"] > self.err_pct_limit:
                self._issue_abort("ERROR_RATE",
                                  f"error_pct={agg['error_pct']} > {self.err_pct_limit} over 5s window")
            if self.p95_limit_ms and agg["p95_ms"] and agg["p95_ms"] > self.p95_limit_ms:
                self._issue_abort("P95_BREACH",
                                  f"p95={agg['p95_ms']}ms > {self.p95_limit_ms}ms over 5s window")
        return snap

    def _running_expected(self):
        return not self.abort_requested

    def _last_data_age(self):
        last = getattr(self.telemetry, "last_data_ts", None)
        return max(0.0, time.time() - last) if last else None

    def _loop(self):
        while not self.stop.is_set():
            try:
                self.evaluate_once()
            except Exception as e:
                self._emit("WARN", f"safety evaluation error: {e}")
            self.stop.wait(2.0)
