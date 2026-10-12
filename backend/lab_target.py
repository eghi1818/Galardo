"""GALARDO - Lab-only target service (Technical Design §1.1 Target).

Web service with /healthz and configurable synthetic degradation endpoints for
safety tests. Binds to 127.0.0.1 only. Degradation is opt-in via control
endpoint - used exclusively to rehearse safety/abort paths inside the lab.
"""
import json
import threading
import time
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {"mode": "healthy", "slow_ms": 800, "error_rate": 0.0}
LOCK = threading.Lock()


class TargetHandler(BaseHTTPRequestHandler):
    server_version = "GalardoLabTarget/1.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        with LOCK:
            mode = STATE["mode"]
            slow_ms = STATE["slow_ms"]
            error_rate = STATE["error_rate"]
        path = self.path.split("?")[0]

        if path == "/control/mode":
            return self._json(200, STATE)

        if path == "/control/degrade":
            # opt-in synthetic degradation (lab rehearsal of safety paths)
            with LOCK:
                STATE["mode"] = "degraded"
                STATE["slow_ms"] = 2500
                STATE["error_rate"] = 0.6
            return self._json(200, {"mode": "degraded", "slow_ms": 2500, "error_rate": 0.6,
                                    "note": "synthetic degradation ACTIVE - for lab rehearsal only"})
        if path == "/control/recover":
            with LOCK:
                STATE.update({"mode": "healthy", "slow_ms": 20, "error_rate": 0.0})
            return self._control_recover()

        if path == "/healthz":
            with LOCK:
                degraded = mode == "degraded"
            if degraded:
                time.sleep(min(slow_ms, 2500) / 1000.0)
                if random.random() < error_rate:
                    return self._json(503, {"status": "degraded", "note": "synthetic fixture"})
            return self._json(200, {"status": "ok", "mode": mode, "ts": time.time()})

        if path in ("/", "/api/slow", "/api/error", "/api/heavy"):
            if mode == "degraded":
                time.sleep(min(slow_ms, 2500) / 1000.0)
                if random.random() < error_rate:
                    return self._json(503, {"status": "degraded"})
            if path == "/api/heavy":
                time.sleep(0.15)
            return self._json(200, {"path": path, "mode": mode, "ts": time.time()})

        return self._json(404, {"error": "not found", "hint": "see allowed_paths in target scope"})

    def _control_recover(self):
        with LOCK:
            STATE.update({"mode": "healthy", "slow_ms": 20, "error_rate": 0.0})
        return self._json(200, {"mode": "healthy", "note": "fixture restored"})


def serve(host="127.0.0.1", port=8088):
    with LOCK:
        STATE.update({"slow_ms": 20})
    httpd = ThreadingHTTPServer((host, port), TargetHandler)
    print(f"[galardo-target] lab target on http://{host}:{port} (/healthz, /api/*, /control/*)")
    httpd.serve_forever()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8088)
    args = ap.parse_args()
    serve(args.host, args.port)
