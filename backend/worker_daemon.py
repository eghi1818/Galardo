"""GALARDO - distributed worker daemon (k6 executor + fleet contract).

Run on each generator VM:
    python3 worker_daemon.py --api http://orchestrator-host:8090 --name w11-jkt-1

Lifecycle (Blueprint §8):
    register -> poll/claim job envelope -> revalidate (hash, allowlist, caps)
    -> run k6 with GALARDO_JOB env -> stream telemetry -> ACK states
    -> abort flag polled at 1s -> SIGTERM -> graceful k6 stop -> flush -> IDLE
Fail-closed: if the API/control channel is unreachable beyond the lease
window while a run is active, the worker kills k6 (stop-on-control-loss).
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

import netssl as _ns

POLL_INTERVAL = 2.0
HEARTBEAT_INTERVAL = 5.0
ABORT_POLL = 1.0
LEASE_GRACE = 20.0  # kill k6 if control channel lost this long during a run

K6_BIN = os.environ.get("GALARDO_K6_BIN", shutil.which("k6") or "k6")


class WorkerDaemon:
    def __init__(self, api, name, k6_bin=K6_BIN):
        self.api = api.rstrip("/")
        self.name = name
        self.k6_bin = k6_bin
        self.status = "IDLE"
        self.current_job = None
        self.stop_flag = threading.Event()
        self.last_control_ok = time.time()
        self.proc = None
        self.capabilities = ["GET", "POST-safe", "ramp", "burst", "weighted-mix",
                             "long-duration", "high-concurrency", "k6"]
        self.expertise = os.environ.get("GALARDO_WORKER_EXPERTISE", "distributed-k6")
        self._sigterm = False
        signal.signal(signal.SIGTERM, self._on_sigterm)
        signal.signal(signal.SIGINT, self._on_sigterm)

    def _on_sigterm(self, *_):
        self._sigterm = True
        self.stop_flag.set()
        self._kill_k6("SIGTERM received")

    # ---------------- control channel ----------------
    def _call(self, method, path, body=None, timeout=10):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.api + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout, context=_ns.context()) as r:
            return json.loads(r.read() or b"{}")

    def register(self):
        r = self._call("POST", "/api/v1/workers", {
            "id": self.name, "name": self.name, "expertise": self.expertise,
            "capabilities": self.capabilities, "kind": "k6-remote",
        })
        print(f"[worker] registered: {self.name} -> {json.dumps(r)[:120]}")

    def heartbeat(self):
        try:
            self._call("POST", f"/api/v1/workers/{self.name}/heartbeat",
                       {"status": self.status, "current_job_id": self.current_job})
            self.last_control_ok = time.time()
            return True
        except Exception:
            return False

    # ---------------- job claim + revalidation ----------------
    def claim_job(self):
        try:
            r = self._call("POST", f"/api/v1/workers/{self.name}/claim", {})
        except Exception:
            return None
        env = r.get("envelope") if isinstance(r, dict) else None
        if env:
            return env
        return None

    def revalidate_envelope(self, env):
        """Fail-closed checks BEFORE any traffic (TD §6 step 8)."""
        errs = []
        if not env.get("job_id") or not env.get("scenario") or not env.get("target_origin"):
            errs.append("envelope incomplete")
        norm = env.get("scenario") or {}
        eff = env.get("effective_policy") or {}
        # hash integrity (self-hash key excluded: hash covers everything but itself)
        norm_copy = {k: v for k, v in norm.items() if k != "scenario_sha256"}
        canon = json.dumps(norm_copy, sort_keys=True).encode()
        if env.get("scenario_sha256") and hashlib.sha256(canon).hexdigest() != env["scenario_sha256"]:
            errs.append("scenario hash mismatch - envelope tampered")
        # host allowlist
        import re as _re
        m = _re.match(r"^https?://([^/:]+)", env.get("target_origin", ""))
        host = m.group(1) if m else ""
        allowed = eff.get("allowed_hosts") or []
        if allowed and host not in allowed:
            errs.append(f"target host '{host}' not in allowlist")
        # caps present (missing = reject)
        for k in ("max_rps", "max_vus", "max_duration_sec"):
            if eff.get(k) in (None, 0):
                errs.append(f"policy cap {k} missing - fail closed")
        # profile within caps
        prof = norm.get("profile") or {}
        if eff.get("max_rps") and (prof.get("max_rps") or 0) > eff["max_rps"]:
            errs.append("scenario rps exceeds effective cap")
        if eff.get("max_vus") and (prof.get("virtual_users") or 0) > eff["max_vus"]:
            errs.append("scenario VUs exceed effective cap")
        if eff.get("max_duration_sec") and (prof.get("duration_seconds") or 0) > eff["max_duration_sec"]:
            errs.append("scenario duration exceeds effective cap")
        return (len(errs) == 0), errs

    # ---------------- k6 execution ----------------
    def run_k6(self, env):
        job_id = env["job_id"]
        workdir = tempfile.mkdtemp(prefix=f"galardo-{job_id}-")
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "k6-worker", "scenario_k6.js")
        script = os.path.abspath(script)
        envd = dict(os.environ)
        envd["GALARDO_JOB"] = json.dumps(env)
        self.proc = subprocess.Popen(
            [self.k6_bin, "run", "--quiet", script],
            env=envd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True, text=True)
        self.last_control_ok = time.time()   # D6: lease starts fresh at job start
        output_tail = []
        deadline_poll = time.time()
        abort_reason = None

        def poll_abort():
            nonlocal abort_reason
            while self.proc and self.proc.poll() is None:
                time.sleep(ABORT_POLL)
                try:
                    st = self._call("GET", f"/api/v1/test-jobs/{job_id}/live")
                    status = st.get("job", {}).get("status")
                    if status in ("ABORT_REQUESTED", "ABORTING"):
                        abort_reason = "abort requested by orchestrator"
                        self._kill_k6(abort_reason)
                        return
                except Exception:
                    # control channel lost during run -> fail closed after grace
                    if time.time() - self.last_control_ok > LEASE_GRACE:
                        abort_reason = f"control channel lost >{LEASE_GRACE}s - fail closed"
                        self._kill_k6(abort_reason)
                        return

        t = threading.Thread(target=poll_abort, daemon=True)
        t.start()
        for line in self.proc.stdout:
            line = line.strip()
            if line:
                output_tail.append(line)
                output_tail[:] = output_tail[-40:]
        self.proc.wait(timeout=120)
        t.join(timeout=2)
        summary = None
        # GALARDO_ENVELOPE_RESULT is followed by a pretty-printed JSON block; capture it whole
        joined = "\n".join(output_tail)
        if "GALARDO_ENVELOPE_RESULT" in joined:
            block = joined.split("GALARDO_ENVELOPE_RESULT", 1)[1]
            # find the outermost {..} block
            start = block.find("{")
            if start >= 0:
                depth = 0
                end = -1
                for i, ch in enumerate(block[start:], start):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                if end > 0:
                    try:
                        summary = json.loads(block[start:end])
                    except Exception:
                        summary = None
        # cleanup temp dir
        shutil.rmtree(workdir, ignore_errors=True)
        return {"exit_code": self.proc.returncode if self.proc else -1,
                "abort_reason": abort_reason, "summary": summary,
                "logs": output_tail[-20:]}

    def _kill_k6(self, reason):
        if self.proc and self.proc.poll() is None:
            print(f"[worker] stopping k6: {reason}")
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                try:
                    self.proc.terminate()
                except Exception:
                    pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:
                    pass

    # ---------------- main loop ----------------
    def run(self):
        print(f"[worker] daemon starting: {self.name} (api={self.api}, k6={self.k6_bin})")
        if not shutil.which(self.k6_bin):
            print(f"[worker] FATAL: k6 binary not found at '{self.k6_bin}'")
            sys.exit(1)
        registered = False
        while not self.stop_flag.is_set():
            try:
                if self.status == "IDLE":
                    if not registered:
                        self.register()
                        registered = True
                    env = self.claim_job()
                    if env:
                        ok, errs = self.revalidate_envelope(env)
                        job_id = env.get("job_id", "?")
                        if not ok:
                            print(f"[worker] envelope REJECTED: {errs}")
                            self._call("POST", f"/api/v1/workers/{self.name}/ack",
                                       {"job_id": job_id, "state": "REJECTED", "reason": errs})
                            # job stays PENDING for another worker/operator; pause briefly
                            time.sleep(5)
                            continue
                        self.status = "RUNNING"
                        self.current_job = job_id
                        self._call("POST", f"/api/v1/workers/{self.name}/ack",
                                   {"job_id": job_id, "state": "READY"})
                        print(f"[worker] RUNNING job {job_id} (hash {env.get('scenario_sha256','')[:12]})")
                        result = self.run_k6(env)
                        self._call("POST", f"/api/v1/workers/{self.name}/ack", {
                            "job_id": job_id, "state": "STOPPED", "result": result})
                        print(f"[worker] job {job_id} finished: exit={result['exit_code']} "
                              f"rps={(result.get('summary') or {}).get('rps')}")
                        self.status = "IDLE"
                        self.current_job = None
                self.heartbeat()
                self.stop_flag.wait(POLL_INTERVAL)
            except Exception as e:
                print(f"[worker] loop error: {e}")
                self.status = "IDLE"
                self.current_job = None
                self.stop_flag.wait(POLL_INTERVAL)
        self.heartbeat()


def main():
    ap = argparse.ArgumentParser(description="GALARDO distributed worker daemon (k6)")
    ap.add_argument("--api", required=True, help="Galardo API base, e.g. http://host:8090")
    ap.add_argument("--name", required=True, help="unique worker id, e.g. w11-jkt-1")
    ap.add_argument("--k6", default=K6_BIN, help="k6 binary path")
    args = ap.parse_args()
    WorkerDaemon(args.api, args.name, args.k6).run()


if __name__ == "__main__":
    main()
