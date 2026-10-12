"""GALARDO - Orchestrator: job state machine, preflight, dispatch, recovery (Technical Design §6, §13).

Job states: PENDING -> PREFLIGHT -> DISPATCHING -> RUNNING -> STOPPING ->
RECOVERY_WAIT -> COMPLETED | RECOVERY_FAILED
Abort: RUNNING -> ABORT_REQUESTED -> ABORTING -> ABORTED -> RECOVERY_WAIT ->
(final) ABORTED with recovery RECOVERED, or RECOVERY_FAILED on timeout.
FAILED: non-recoverable pre-run/execution error (hard terminal).

State transition guard: hard-terminal states never mutate again; ABORTED only
re-enters RECOVERY_WAIT. Abort is idempotent (FR-06). Recovery is judged by the
INDEPENDENT probe, never by worker completion (FR-08). No automatic traffic
re-run after ambiguous outcome (Blueprint §6.1).
"""
import threading
import time

import db
import fleet
try:
    import webhooks
except Exception:
    webhooks = None
from engine import LoadEngine, TelemetryRing
from safety import HealthProbe, SafetyController
from util import now_iso, now_ts, gen_id, gen_correlation_id

JOBS = {}          # job_id -> RuntimeCtx
JOBS_LOCK = threading.Lock()

HARD_TERMINAL = {"COMPLETED", "FAILED", "RECOVERY_FAILED", "REJECTED"}
ALLOWED_AFTER_ABORTED = {"RECOVERY_WAIT"}


class RuntimeCtx:
    def __init__(self, job_id):
        self.job_id = job_id
        self.engine = None
        self.probe = None
        self.safety = None
        self.telemetry = None
        self.abort_requested = False
        self.abort_reason_code = None
        self.abort_acked = False
        self.abort_ack_at = None
        self.thread = None
        self.probe_series = []
        self.timeline = []
        self.recovery_thread = None
        self.recovery_id = None
        self.worker = None
        self.worker_required = []
        self.worker_score = 0


def _set_state(job_id, new_state, actor="orchestrator", action=None, reason="", correlation_id=None):
    """Guarded state transition. Returns True if applied."""
    old = db.get("test_jobs", job_id)
    old_state = old.get("status") if old else None
    if old_state == new_state:
        return False
    if old_state in HARD_TERMINAL:
        db.audit_event("orchestrator", "state.transition_blocked", "test_job", job_id,
                       reason=f"refused {old_state} -> {new_state} (hard terminal)", correlation_id=correlation_id)
        return False
    if old_state == "ABORTED" and new_state not in ALLOWED_AFTER_ABORTED:
        db.audit_event("orchestrator", "state.transition_blocked", "test_job", job_id,
                       reason=f"refused {old_state} -> {new_state}", correlation_id=correlation_id)
        return False

    def mut(j):
        j["status"] = new_state
        if new_state == "RUNNING" and not j.get("started_at"):
            j["started_at"] = now_iso()
        if new_state in HARD_TERMINAL and not j.get("ended_at"):
            j["ended_at"] = now_iso()
        if new_state == "ABORT_REQUESTED":
            j["abort_requested_at"] = now_iso()
        if new_state == "ABORTED":
            j["abort_confirmed_at"] = j.get("abort_confirmed_at") or now_iso()
    db.update("test_jobs", job_id, mut, actor=actor,
              action=action or f"job.state.{new_state.lower()}", resource_type="test_job",
              reason=reason or f"{old_state} -> {new_state}", correlation_id=correlation_id)
    db.observation(job_id, "orchestrator", "INFO" if new_state not in ("FAILED", "RECOVERY_FAILED") else "WARN",
                   f"state: {old_state} -> {new_state}" + (f" ({reason})" if reason else ""),
                   correlation_id=correlation_id)
    # external webhook hooks (fire-and-forget, never blocks the state machine)
    if webhooks and new_state in ("COMPLETED", "ABORTED", "FAILED", "RECOVERY_FAILED"):
        j = db.get("test_jobs", job_id) or {}
        webhooks.fire(
            "job.completed" if new_state == "COMPLETED" else "job.aborted" if new_state == "ABORTED" else "job.failed",
            {"job_id": job_id, "status": new_state, "plan": j.get("test_plan_id"),
             "abort_code": j.get("abort_code"), "abort_reason": j.get("abort_reason"),
             "started_at": j.get("started_at"), "ended_at": j.get("ended_at"),
             "correlation_id": correlation_id})
    return True


# ---------------------------------------------------------------------------
# Preflight (Dashboard UX §6 checklist)
# ---------------------------------------------------------------------------
def run_preflight(job_id):
    job = db.get("test_jobs", job_id)
    plan = db.get("test_plans", job.get("test_plan_id") or "") if job else None
    checks = []

    def add(name, ok, reason, source, mandatory=True):
        checks.append({"check": name, "result": "PASS" if ok else ("FAIL" if ok is False else "UNKNOWN"),
                       "reason": reason, "source": source, "at": now_iso(), "mandatory": mandatory})

    if not job or not plan:
        add("job & plan exist", False, "job or test plan missing", "api")
        return checks

    eng = db.get("engagements", plan.get("engagement_id") or "")
    tgt = db.get("targets", plan.get("target_id") or "")
    scv = db.get("scenario_versions", plan.get("scenario_version_id") or "")
    pol = db.get("safety_policies", plan.get("policy_version_id") or "")

    add("engagement approved & active",
        bool(eng) and eng.get("status") == "APPROVED",
        f"engagement status={eng.get('status') if eng else 'MISSING'}", "db")
    add("target verified",
        bool(tgt) and tgt.get("status") == "VERIFIED",
        f"target status={tgt.get('status') if tgt else 'MISSING'}", "db")
    add("target within validity window",
        bool(tgt) and _in_window(tgt),
        f"valid {tgt.get('valid_from')}..{tgt.get('valid_until')}" if tgt else "target missing", "db")
    add("scenario version immutable & validated",
        bool(scv) and scv.get("review_status") in ("VALIDATED", "APPROVED"),
        f"version {scv.get('version_no') if scv else 'MISSING'} hash={str(scv.get('content_sha256', ''))[:12] if scv else ''}", "db")
    add("policy version approved",
        bool(pol) and pol.get("status") in ("APPROVED", "SUPERSEDED", "ACTIVE"),
        f"policy status={pol.get('status') if pol else 'MISSING'}", "db")
    add("test plan APPROVED",
        plan.get("status") == "APPROVED",
        f"plan status={plan.get('status')}", "db")
    add("no conflicting active job",
        not _conflicting_active_job(job_id, plan.get("target_id")),
        "one active job per target", "db")
    add("abort route available",
        True, "in-process abort channel registered at dispatch", "orchestrator")
    return checks


def _in_window(tgt):
    try:
        now = now_ts()
        return _iso_ts(tgt.get("valid_from")) <= now <= _iso_ts(tgt.get("valid_until"))
    except Exception:
        return False


def _iso_ts(s):
    from datetime import datetime, timezone
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() if s else 0


def _conflicting_active_job(job_id, target_id):
    actives = db.list("test_jobs", lambda j: j.get("id") != job_id and j.get("status") in (
        "PENDING", "PREFLIGHT", "DISPATCHING", "RUNNING", "ABORT_REQUESTED", "ABORTING", "STOPPING", "RECOVERY_WAIT"))
    for j in actives:
        p = db.get("test_plans", j.get("test_plan_id") or "")
        if p and p.get("target_id") == target_id:
            return True
    return False


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------
def create_job(test_plan_id, requested_by, idempotency_key=None):
    """Idempotent job creation (FR-05): same key returns same job."""
    existing = db.list("test_jobs", lambda j: j.get("idempotency_key") == idempotency_key) if idempotency_key else []
    if existing:
        return existing[0], False

    plan = db.get("test_plans", test_plan_id)
    if not plan:
        raise ValueError("test plan not found")
    if plan.get("status") != "APPROVED":
        raise ValueError(f"test plan not APPROVED (status={plan.get('status')})")

    job_id = gen_id("job")
    job = {
        "id": job_id,
        "test_plan_id": test_plan_id,
        "engagement_id": plan.get("engagement_id"),
        "idempotency_key": idempotency_key or f"auto-{job_id}",
        "requested_by": requested_by,
        "status": "PENDING",
        "correlation_id": gen_correlation_id(),
        "created_at": now_iso(),
        "started_at": None, "ended_at": None,
        "abort_reason": None, "abort_code": None,
        "evidence_id": None, "final_metrics": None,
        "preflight": None,
    }
    db.insert("test_jobs", job, actor=requested_by, action="job.created",
              resource_type="test_job", reason=f"plan={test_plan_id}",
              correlation_id=job["correlation_id"])
    return job, True


def start_job(job_id, actor="operator"):
    """Preflight then dispatch. Fail-closed: any non-PASS mandatory check blocks start."""
    job = db.get("test_jobs", job_id)
    if not job:
        return False, [{"check": "job", "result": "FAIL", "reason": "not found", "mandatory": True}]
    if job["status"] not in ("PENDING",):
        return False, [{"check": "state", "result": "FAIL",
                        "reason": f"job in state {job['status']}, only PENDING can start", "mandatory": True}]

    _set_state(job_id, "PREFLIGHT", actor=actor)
    checks = run_preflight(job_id)
    db.update("test_jobs", job_id, lambda j: j.update({"preflight": checks}), audit=False)
    failed = [c for c in checks if c["mandatory"] and c["result"] != "PASS"]
    if failed:
        # soft-terminal: no traffic ever dispatched; operator may inspect and re-create.
        # (Job creation is idempotent by key, so a new attempt = new idempotency key.)
        _set_state(job_id, "REJECTED", actor=actor, reason=f"preflight failed: {failed[0]['check']}")
        return False, checks

    _set_state(job_id, "DISPATCHING", actor=actor, reason="preflight all PASS; reserving execution slot")
    ctx = RuntimeCtx(job_id)
    with JOBS_LOCK:
        JOBS[job_id] = ctx
    ctx.thread = threading.Thread(target=_execute, args=(job_id,), daemon=True,
                                  name=f"job-{job_id[:12]}")
    ctx.thread.start()
    return True, checks


def abort_job(job_id, reason, actor="operator", code="MANUAL_ABORT"):
    """Idempotent abort (FR-06). Returns (status_after, info)."""
    job = db.get("test_jobs", job_id)
    if not job:
        return None, {"error": "job not found"}
    correlation_id = job.get("correlation_id")

    if job["status"] in ("COMPLETED", "FAILED", "RECOVERY_FAILED", "ABORTED"):
        db.audit_event(actor, "abort.ignored_terminal", "test_job", job_id,
                       reason=f"job already terminal ({job['status']})", correlation_id=correlation_id)
        return job["status"], {"ack": False, "note": f"already terminal: {job['status']}"}
    if job["status"] == "RECOVERY_WAIT":
        db.audit_event(actor, "abort.ignored_recovery", "test_job", job_id,
                       reason="no traffic flowing during recovery wait", correlation_id=correlation_id)
        return job["status"], {"ack": True, "note": "job in RECOVERY_WAIT - nothing to abort"}

    with JOBS_LOCK:
        ctx = JOBS.get(job_id)
        if ctx:
            if not ctx.abort_requested:
                ctx.abort_requested = True
                ctx.abort_reason_code = code
            else:
                db.audit_event(actor, "abort.idempotent_repeat", "test_job", job_id,
                               reason=f"repeat abort ignored (already requested): {reason}",
                               correlation_id=correlation_id)
                cur = db.get("test_jobs", job_id)
                return cur.get("status") if cur else None, {"idempotent": True, "ack": ctx.abort_acked}
            if ctx.engine:
                ctx.engine.stop.set()

    if job["status"] in ("PENDING", "PREFLIGHT", "DISPATCHING"):
        _set_state(job_id, "ABORT_REQUESTED", actor=actor, reason=f"[{code}] {reason}",
                   correlation_id=correlation_id)
        _set_state(job_id, "ABORTING", actor=actor, reason="no traffic started yet",
                   correlation_id=correlation_id)
        _set_state(job_id, "ABORTED", actor=actor, reason=f"[{code}] {reason}",
                   correlation_id=correlation_id)
        db.update("test_jobs", job_id, lambda j: j.update({
            "abort_reason": reason, "abort_code": code}),
            actor=actor, action="job.abort_recorded", resource_type="test_job",
            reason=reason, correlation_id=correlation_id)
        # abort pre-run still enters recovery wait (target untouched, recovers trivially)
        _begin_recovery(job_id, actor=actor)
        return "ABORTED", {"ack": True, "note": "job never started traffic"}

    # RUNNING / ABORT_REQUESTED / ABORTING / STOPPING
    if job["status"] != "ABORT_REQUESTED":
        _set_state(job_id, "ABORT_REQUESTED", actor=actor, reason=f"[{code}] {reason}",
                   correlation_id=correlation_id)
    db.update("test_jobs", job_id, lambda j: j.update({
        "abort_reason": j.get("abort_reason") or reason, "abort_code": j.get("abort_code") or code}),
        audit=False)

    deadline = time.time() + 8
    acked = False
    while time.time() < deadline:
        with JOBS_LOCK:
            ctx = JOBS.get(job_id)
            if ctx and ctx.abort_acked:
                acked = True
                break
        time.sleep(0.2)
    cur = db.get("test_jobs", job_id)
    return (cur.get("status") if cur else None), {"ack": acked,
           "note": "engine acknowledged stop" if acked else "waiting for engine stop; watchdog will enforce"}


# ---------------------------------------------------------------------------
# Recovery monitor (FR-08, Technical Design §13)
# ---------------------------------------------------------------------------
def _begin_recovery(job_id, actor="orchestrator"):
    """Move job into RECOVERY_WAIT and start the independent-probe monitor."""
    job = db.get("test_jobs", job_id)
    if not job:
        return None
    if job["status"] in HARD_TERMINAL:
        return job["status"]
    _set_state(job_id, "RECOVERY_WAIT", actor=actor, reason="waiting for target recovery criteria")

    ctx = JOBS.get(job_id)
    if ctx and ctx.recovery_thread and ctx.recovery_thread.is_alive():
        return "RECOVERY_WAIT"

    target = None
    plan = db.get("test_plans", job.get("test_plan_id") or "")
    if plan:
        target = db.get("targets", plan.get("target_id") or "")
    timeout_sec = (target or {}).get("recovery_timeout_sec", 60)

    rec_id = gen_id("rec")
    if ctx:
        ctx.recovery_id = rec_id
    rec = {"id": rec_id, "job_id": job_id, "started_at": now_iso(), "completed_at": None,
           "status": "RECOVERING",
           "criteria_json": {"source": "independent_probe", "required_state": "HEALTHY",
                             "consecutive_healthy": 3, "timeout_sec": timeout_sec},
           "observation_refs": []}
    db.insert("recoveries", rec, actor=actor, action="recovery.started",
              resource_type="recovery", reason=f"job={job_id}")

    was_aborted = bool(job.get("abort_code"))

    def _recover_thread():
        healthy_streak = 0
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            snap = ctx.probe.snapshot() if (ctx and ctx.probe) else {"state": "UNKNOWN"}
            if snap.get("state") == "HEALTHY":
                healthy_streak += 1
            else:
                healthy_streak = 0
            if healthy_streak >= 3:
                db.update("recoveries", rec_id, lambda r: r.update({
                    "status": "RECOVERED", "completed_at": now_iso()}),
                    actor="orchestrator", action="recovery.recovered", resource_type="recovery")
                if was_aborted:
                    _set_state(job_id, "ABORTED", actor="orchestrator",
                               reason="recovery criteria met (independent probe HEALTHY x3); final status ABORTED")
                else:
                    _set_state(job_id, "COMPLETED", actor="orchestrator",
                               reason="recovery criteria met (independent probe HEALTHY x3)")
                with JOBS_LOCK:
                    if ctx and ctx.probe:
                        ctx.probe.stop.set()  # probe duty done
                return
            time.sleep(1.0)
        db.update("recoveries", rec_id, lambda r: r.update({
            "status": "RECOVERY_FAILED", "completed_at": now_iso()}),
            actor="orchestrator", action="recovery.failed", resource_type="recovery",
            reason=f"target not HEALTHY x3 within {timeout_sec}s")
        _set_state(job_id, "RECOVERY_FAILED", actor="orchestrator",
                   reason="recovery timeout - target did not return to HEALTHY")
        with JOBS_LOCK:
            if ctx and ctx.probe:
                ctx.probe.stop.set()

    # Remote (k6) execution has no in-process probe: spawn a standalone one so
    # recovery stays verified by an INDEPENDENT probe (TD §10), not worker claims.
    if not (ctx and ctx.probe):
        job2 = db.get("test_jobs", job_id)
        plan2 = db.get("test_plans", (job2 or {}).get("test_plan_id") or "")
        tgt2 = db.get("targets", (plan2 or {}).get("target_id") or "") if plan2 else None
        if tgt2:
            contract = tgt2.get("probe_contract") or {
                "url": tgt2["canonical_origin"] + "/", "expected_status": 200,
                "interval_sec": 2, "timeout_sec": 2.0, "failure_threshold": 3}
            standalone = HealthProbe(job_id, contract,
                                     interval=contract.get("interval_sec", 2.0),
                                     timeout=contract.get("timeout_sec", 2.0),
                                     failure_threshold=contract.get("failure_threshold", 3))
            standalone.start()
            if ctx is None:
                ctx = RuntimeCtx(job_id)
                with JOBS_LOCK:
                    JOBS[job_id] = ctx
            ctx.probe = standalone

    # probe must be alive to verify recovery; UNKNOWN is unsafe (fail-closed)
    if not (ctx and ctx.probe and ctx.probe.is_alive()):
        db.update("recoveries", rec_id, lambda r: r.update({
            "status": "RECOVERY_FAILED", "completed_at": now_iso()}),
            actor="orchestrator", action="recovery.failed", resource_type="recovery",
            reason="probe unavailable - recovery cannot be verified")
        _set_state(job_id, "RECOVERY_FAILED", actor="orchestrator",
                   reason="probe unavailable; recovery unverifiable (fail-closed)")
        return "RECOVERY_FAILED"

    ctx.recovery_thread = threading.Thread(target=_recover_thread, daemon=True,
                                           name=f"recovery-{job_id[:12]}")
    ctx.recovery_thread.start()
    return "RECOVERY_WAIT"


def monitor_recovery(job_id, actor="operator"):
    """Public recovery entrypoint. Idempotent; returns current job status."""
    job = db.get("test_jobs", job_id)
    if not job:
        return None
    if job["status"] in ("ABORTED", "STOPPING", "RECOVERY_WAIT"):
        return _begin_recovery(job_id, actor=actor)
    return job["status"]


# ---------------------------------------------------------------------------
# Execution thread
# ---------------------------------------------------------------------------
def _execute(job_id):
    ctx = JOBS[job_id]
    job = db.get("test_jobs", job_id)
    correlation_id = job["correlation_id"]
    plan = db.get("test_plans", job["test_plan_id"])
    scv = db.get("scenario_versions", plan["scenario_version_id"])
    norm = scv["normalized_json"]
    target = db.get("targets", plan["target_id"])
    pol = db.get("safety_policies", plan["policy_version_id"])

    try:
        from policy import effective_policy, load_policy_layers
        layers = load_policy_layers(db, plan.get("engagement_id"))
        layers.append(pol)
        eff, _ = effective_policy(layers)
        eff["max_rps"] = min(eff["max_rps"] or norm["profile"]["max_rps"], norm["profile"]["max_rps"])
        eff["max_vus"] = min(eff["max_vus"] or norm["profile"]["virtual_users"], norm["profile"]["virtual_users"])
        eff["max_duration_sec"] = min(eff["max_duration_sec"] or norm["profile"]["duration_seconds"],
                                      norm["profile"]["duration_seconds"])

        _set_state(job_id, "RUNNING", actor="orchestrator",
                   reason=f"worker slot acquired; effective caps rps={eff['max_rps']} vus={eff['max_vus']} dur={eff['max_duration_sec']}s",
                   correlation_id=correlation_id)

        # capability-based worker assignment (fleet scheduling)
        w, required, score = fleet.pick_worker(norm)
        if w:
            ctx.worker = w
            ctx.worker_required = list(required)
            ctx.worker_score = score
            fleet.set_status(w["id"], "RUNNING", job_id=job_id)
            db.observation(job_id, "orchestrator", "INFO",
                           f"worker assigned: {w['id']} ({w['name']}, expertise={w['expertise']}, "
                           f"match {score}/{len(required)} caps {required})",
                           correlation_id=correlation_id)

        ctx.telemetry = TelemetryRing()
        probe_contract = target.get("probe_contract") or {}
        if not probe_contract.get("url"):
            probe_contract = {"url": target["canonical_origin"] + "/healthz",
                              "expected_status": 200, "interval_sec": 1, "timeout_sec": 0.8,
                              "failure_threshold": 3}
        ctx.probe = HealthProbe(job_id, probe_contract,
                                interval=probe_contract.get("interval_sec", 1.0),
                                timeout=probe_contract.get("timeout_sec", 0.8),
                                failure_threshold=probe_contract.get("failure_threshold", 3))
        ctx.probe.start()
        # baseline: probe must be HEALTHY before traffic (fail-closed, blueprint runbook)
        baseline_wait = time.time() + 8
        while time.time() < baseline_wait and ctx.probe.state == "UNKNOWN":
            time.sleep(0.3)
        db.observation(job_id, "probe", "INFO", f"baseline probe state={ctx.probe.state}",
                       correlation_id=correlation_id)
        if ctx.probe.state != "HEALTHY":
            raise RuntimeError(f"probe baseline not HEALTHY (state={ctx.probe.state}); fail-closed")

        def on_safety_event(sev, msg, snap):
            db.observation(job_id, "safety", sev, msg, metric_snapshot=snap,
                           correlation_id=correlation_id)

        def abort_fn(reason_code, detail):
            cur = db.get("test_jobs", job_id)
            if cur and cur.get("status") in HARD_TERMINAL:
                return False  # too late to transition; guard holds
            with JOBS_LOCK:
                ctx.abort_requested = True
                ctx.abort_reason_code = ctx.abort_reason_code or reason_code
                if ctx.engine:
                    ctx.engine.stop.set()
            db.observation(job_id, "safety", "CRIT", f"safety abort dispatched [{reason_code}] {detail}",
                           correlation_id=correlation_id)
            _set_state(job_id, "ABORT_REQUESTED", actor="safety-controller",
                       reason=f"[{reason_code}] {detail}", correlation_id=correlation_id)
            # persist abort reason onto the job immediately so finalization
            # can never mistake a safety-aborted run for a clean completion
            db.update("test_jobs", job_id, lambda j: j.update({
                "abort_reason": j.get("abort_reason") or detail,
                "abort_code": j.get("abort_code") or reason_code}), audit=False)
            return True

        ctx.safety = SafetyController(job_id, pol, ctx.probe, ctx.telemetry, abort_fn,
                                      on_event=on_safety_event,
                                      telemetry_stale_sec=max(6, min(15, eff["max_duration_sec"] / 4)),
                                      startup_grace_sec=min(15, max(6, eff["max_duration_sec"] / 4)))
        ctx.safety.start()

        ctx.engine = LoadEngine(job_id, f"run-{job_id}", target["canonical_origin"], norm,
                                eff, ctx.telemetry,
                                abort_check=lambda: (ctx.abort_requested, ctx.abort_reason_code))
        run_id = gen_id("run")
        run_doc = {
            "id": run_id, "job_id": job_id, "attempt_no": 1,
            "worker_id": ctx.worker["id"] if ctx.worker else "in-process-1",
            "worker_name": ctx.worker["name"] if ctx.worker else "in-process bounded engine",
            "scenario_hash": scv["content_sha256"],
            "policy_hash": pol.get("policy_sha256"),
            "started_at": now_iso(), "ended_at": None, "exit_code": None, "result_json": None,
        }
        db.insert("test_runs", run_doc, actor="orchestrator", action="run.started",
                  resource_type="test_run", reason=f"job={job_id}", correlation_id=correlation_id)

        result = ctx.engine.run()
        ctx.abort_acked = True
        ctx.abort_ack_at = now_iso()

        aborted = ctx.abort_requested
        _set_state(job_id, "ABORTING" if aborted else "STOPPING", actor="worker",
                   reason="engine stopped; flushing final metrics" if aborted else "scenario duration reached",
                   correlation_id=correlation_id)
        ctx.safety.stop_controller()  # no further evaluation once traffic stopped

        final = {
            "aggregate": ctx.telemetry.window(max(5, int(result["duration_actual"]) or 5)),
            "engine": result,
            "effective_policy": dict(eff),
            "probe_final": ctx.probe.snapshot(),
            "safety_decisions": ctx.safety.decisions[-50:],
        }
        ctx.probe_series = ctx.probe.history[:]
        ctx.timeline = [{"at": d["at"], "severity": d["severity"], "message": d["message"]}
                        for d in ctx.safety.decisions[-100:]]
        db.update("test_jobs", job_id, lambda j: j.update({"final_metrics": final}), audit=False)
        db.update("test_runs", run_id, lambda r: r.update({
            "ended_at": now_iso(), "exit_code": 2 if aborted else 0,
            "result_json": {"aggregate": final["aggregate"], "abort_reason": result["abort_reason"]},
            "probe_series": ctx.probe_series, "timeline": ctx.timeline}), audit=False)

        if aborted:
            db.audit_event("worker", "abort.worker_ack", "test_job", job_id,
                           reason=f"abort acknowledged at {ctx.abort_ack_at} [{ctx.abort_reason_code}]",
                           correlation_id=correlation_id)
            _set_state(job_id, "ABORTED", actor="worker",
                       reason=f"engine ACK stop [{ctx.abort_reason_code}]; metrics flushed",
                       correlation_id=correlation_id)
        else:
            db.audit_event("worker", "run.completed", "test_job", job_id,
                           reason="scenario finished within bounds", correlation_id=correlation_id)
        if ctx.worker:
            fleet.set_status(ctx.worker["id"], "IDLE", job_id=None)

        # FR-08: after normal stop/abort the system waits for recovery automatically
        _begin_recovery(job_id, actor="orchestrator")
    except Exception as e:
        db.observation(job_id, "orchestrator", "CRIT", f"execution error: {e}",
                       correlation_id=correlation_id)
        _set_state(job_id, "FAILED", actor="orchestrator", reason=str(e)[:300],
                   correlation_id=correlation_id)
        if ctx.worker:
            fleet.set_status(ctx.worker["id"], "IDLE", job_id=None)
        with JOBS_LOCK:
            if ctx.probe:
                ctx.probe.stop.set()
            if ctx.safety:
                ctx.safety.stop_controller()


def get_runtime_snapshot(job_id):
    """Live snapshot for dashboard."""
    job = db.get("test_jobs", job_id)
    if not job:
        return None
    ctx = JOBS.get(job_id)
    snap = {
        "job": job, "live": False, "telemetry": None, "timeseries": None,
        "probe": None, "vus": None, "safety": None, "recovery": None,
    }
    recs = db.list("recoveries", lambda r: r.get("job_id") == job_id)
    if recs:
        snap["recovery"] = sorted(recs, key=lambda r: r.get("started_at") or "")[-1]
    if ctx:
        snap["worker"] = (dict(ctx.worker, required_capabilities=ctx.worker_required,
                               match_score=ctx.worker_score) if ctx.worker else None)
    if ctx and ctx.telemetry:
        snap["live"] = True
        snap["telemetry"] = ctx.telemetry.window(10)
        snap["timeseries"] = ctx.telemetry.timeseries(90, 2)
        if ctx.probe:
            snap["probe"] = ctx.probe.snapshot()
        with JOBS_LOCK:
            snap["vus"] = max([s for _, s in ctx.telemetry.series.get("active_vus", [])[-20:]] or [0])
        if ctx.safety:
            snap["safety"] = {"decisions": ctx.safety.decisions[-20:],
                              "abort_requested": ctx.safety.abort_requested}
    else:
        fm = job.get("final_metrics") or {}
        snap["telemetry"] = fm.get("aggregate")
        snap["probe"] = fm.get("probe_final")
        runs = db.list("test_runs", lambda r: r.get("job_id") == job_id)
        if runs:
            last = sorted(runs, key=lambda r: r.get("started_at") or "")[-1]
            snap["safety"] = {"decisions": last.get("timeline") or []}
    return snap
