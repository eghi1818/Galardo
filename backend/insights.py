"""GALARDO - AI advisory insights (deterministic rules engine, Governance §1-2).

Advisory only: generates human-readable insights from measured evidence
(telemetry, probe, observations, abort records). No dispatch credentials, no
policy mutation. Every insight carries severity, detail, evidence refs, and a
confidence tag; UI must present them as advisory, never as measured fact.
"""
from util import now_iso
import time

MODEL = "galardo-rules-engine-v1 (deterministic, advisory)"


def analyze_job(job_id, orchestrator_mod=None):
    import db
    job = db.get("test_jobs", job_id)
    if not job:
        return None

    ctx = orchestrator_mod.JOBS.get(job_id) if orchestrator_mod else None
    # live only while the run is actively producing fresh telemetry;
    # a finished job whose ring has aged out must use FINAL metrics instead
    fresh = bool(ctx and ctx.telemetry and getattr(ctx.telemetry, "last_data_ts", None)
                 and (time.time() - ctx.telemetry.last_data_ts) < 15)
    running_states = ("RUNNING", "ABORT_REQUESTED", "ABORTING", "DISPATCHING")
    live = bool(ctx and ctx.telemetry and job.get("status") in running_states and fresh)
    if live:
        agg = ctx.telemetry.window(30)
        probe = ctx.probe.snapshot() if ctx.probe else None
        series = ctx.telemetry.timeseries(60, 2)
        vus = None
        if ctx.telemetry.series.get("active_vus"):
            vus = max(s for _, s in ctx.telemetry.series["active_vus"][-20:])
    else:
        fm = job.get("final_metrics") or {}
        agg = dict(fm.get("aggregate") or {})
        probe = fm.get("probe_final")
        series = None
        vus = None

    ins = []
    total = agg.get("requests") or 0
    rps = agg.get("rps") or 0
    p95 = agg.get("p95_ms")
    err_pct = agg.get("error_pct") or 0.0
    conn = agg.get("conn_errors") or 0
    timeouts = agg.get("timeouts") or 0
    e5 = agg.get("err_5xx") or 0
    e4 = agg.get("err_4xx") or 0

    def add(sev, title, detail, evidence=None, confidence="rule-based"):
        ins.append({"severity": sev, "title": title, "detail": detail,
                    "evidence": evidence or {}, "confidence": confidence})

    # 1. connection-level degradation
    if conn > 0 or timeouts > 0:
        sev = "CRIT" if (conn + timeouts) and total and (conn + timeouts) / total > 0.05 else "WARN"
        kind = "Connection Timeout/Reset" if conn >= timeouts else "Slow responses exceeding timeout"
        add(sev, f"Target degraded at {rps} rps due to {kind}",
            f"{conn + timeouts} of {total} requests failed at transport level "
            f"(conn_errors={conn}, timeouts={timeouts}) while pushing {rps} rps. "
            f"Target likely saturated or dropping connections under this profile.",
            {"rps": rps, "conn_errors": conn, "timeouts": timeouts, "requests": total})
    # 2. server errors
    if total and e5:
        pct = round(100.0 * e5 / total, 2)
        add("CRIT" if pct > 5 else "WARN", f"HTTP 5xx spike ({pct}%)",
            f"{e5} server errors at {rps} rps. Indicates saturation or failing "
            f"dependency behind the target - not a client-side artifact.",
            {"err_5xx": e5, "pct": pct, "rps": rps})
    # 3. client errors
    if total and e4:
        pct = round(100.0 * e4 / total, 2)
        add("WARN" if pct > 5 else "INFO", f"HTTP 4xx responses ({pct}%)",
            f"{e4} client errors - usually request validity (path/method/params), "
            f"not capacity. Review scenario against target contract.",
            {"err_4xx": e4, "pct": pct})
    # 4. p95 trend (live series only)
    if series and len(series) >= 8:
        half = len(series) // 2
        a = [d["p95"] for d in series[:half] if d["p95"] is not None]
        b = [d["p95"] for d in series[half:] if d["p95"] is not None]
        if a and b:
            am, bm = sum(a) / len(a), sum(b) / len(b)
            if am > 0 and bm > am * 1.3:
                add("WARN", f"p95 degraded {am:.0f}→{bm:.0f} ms (+{(bm / am - 1) * 100:.0f}%)",
                    f"Latency trend worsened during the run - degradation began as load "
                    f"accumulated. Watch for a capacity ceiling below the configured cap.",
                    {"p95_first_half_ms": round(am, 1), "p95_second_half_ms": round(bm, 1)})
            elif bm <= am * 1.1 and bm is not None:
                add("OK", f"p95 stable (~{bm:.0f} ms)",
                    f"Latency held steady across the run (first-half {am:.0f} ms vs "
                    f"second-half {bm:.0f} ms).",
                    {"p95_first_half_ms": round(am, 1), "p95_second_half_ms": round(bm, 1)})
    # 5. probe state
    if probe and probe.get("state") and probe["state"] != "HEALTHY":
        add("CRIT" if probe["state"] in ("DEGRADED", "ABORT_REQUESTED") else "WARN",
            f"Independent probe: {probe['state']}",
            f"Probe recorded {probe.get('consecutive_failures')} consecutive failures "
            f"(last error: {probe.get('last_error') or 'n/a'}). Probe is independent "
            f"of traffic - target health genuinely affected.",
            {"probe_state": probe["state"], "consecutive_failures": probe.get("consecutive_failures")})
    # 6. abort record
    if job.get("abort_code"):
        add("CRIT", f"Run auto-aborted [{job['abort_code']}]",
            f"Safety controller stopped the run: {job.get('abort_reason')}. "
            f"Worker ACK and recovery verification are recorded in the timeline.",
            {"abort_code": job["abort_code"]})
    # 7. throughput vs cap
    eff = (job.get("final_metrics") or {}).get("effective_policy") or {}
    cap = eff.get("max_rps")
    if cap and total:
        if rps < cap * 0.6 and (vus or 0) >= (eff.get("max_vus") or 1):
            add("INFO", f"Throughput plateau at {rps} rps (cap {cap})",
                f"Client-side pacing (VUs={vus}, think time) is the limiting factor, "
                f"not target capacity. Increase VUs or reduce think time - within policy - "
                f"to probe higher load.",
                {"rps": rps, "cap": cap, "vus": vus})
        elif rps >= cap * 0.9 and err_pct < 1:
            add("OK", f"Sustained {rps} rps at ≥90% of cap with {err_pct}% errors",
                f"Target absorbed near-cap load with stable latency profile "
                f"(p95 {p95} ms).",
                {"rps": rps, "cap": cap, "p95_ms": p95})
    # 8. capacity estimate (terminal, clean run) — DITOLAK bila k6 failed rate tinggi
    k6_failed = (job.get("final_metrics") or {}).get("aggregate", {}).get("failed_rate")
    clean = (k6_failed is None or k6_failed < 0.10) and err_pct < 5
    if not live and total and clean and p95 is not None:
        win = agg.get("window_seconds") or 0
        add("OK", f"Estimated safe capacity ≥ {rps} rps (this profile)",
            f"No degradation across {total} requests over {win:.0f}s. Safe capacity is "
            f"AT LEAST this level for the current scenario shape; raise profile "
            f"incrementally to find the ceiling. Estimate is profile-specific, not absolute.",
            {"rps": rps, "requests": total, "window_seconds": win}, confidence="heuristic")
    # 9. all-clear — HANYA bila benar-benar bersih (Improvement B2: timeout & failed
    # rate tinggi tidak boleh lolos sebagai "No degradation")
    if not ins and total:
        add("OK", "No degradation signals detected",
            f"{total} requests at {rps} rps, p95 {p95} ms, error rate {err_pct}% - "
            f"target healthy within the bounded profile.",
            {"requests": total, "p95_ms": p95, "error_pct": err_pct})
    # 10. k6 failed_rate (timeout-based) — sering tersembunyi dari telemetry ring
    # yang hanya menghitung conn/timeout dari engine in-process. Bila job punya
    # k6 failed_rate > 20%, itu DEGRADATION, bukan all-clear.
    fm = job.get("final_metrics") or {}
    k6_failed = (fm.get("aggregate") or {}).get("failed_rate")
    if k6_failed is not None and k6_failed > 0.20:
        add("CRIT" if k6_failed > 0.5 else "WARN",
            f"k6 failed rate {round(k6_failed*100,1)}% - connection/timeout saturation",
            f"Load generator recorded {round(k6_failed*100,1)}% failed requests "
            f"(mostly timeouts at configured limit). Combined with error telemetry, "
            f"this indicates saturation of the connection path - NOT a healthy run. "
            f"Treat capacity numbers from this run as upper-bound only.",
            {"failed_rate": round(k6_failed, 3), "requests": total, "rps": rps},
            confidence="heuristic")
        # downgrade an all-clear if it was emitted
        for i in ins:
            if i["title"] == "No degradation signals detected":
                i["severity"] = "WARN"
                i["title"] = f"Degradation: {round(k6_failed*100,1)}% failed (k6) - not all-clear"
                i["detail"] = (f"Initial rule found no in-process degradation signals, but k6 "
                               f"failed_rate {round(k6_failed*100,1)}% exceeds threshold. "
                               f"See the CRIT/WARN finding above.")
                i["severity"] = "CRIT" if k6_failed > 0.5 else "WARN"
        order = {"CRIT": 0, "WARN": 1, "INFO": 2, "OK": 3}
        ins.sort(key=lambda x: order.get(x["severity"], 9))
    if not total:
        add("INFO", "No traffic observed",
            "Job has not generated measurable requests yet (or telemetry is empty). "
            "UNKNOWN is treated as unsafe by the safety controller.",
            {})

    order = {"CRIT": 0, "WARN": 1, "INFO": 2, "OK": 3}
    ins.sort(key=lambda x: order.get(x["severity"], 9))
    worst = ins[0]["severity"] if ins else "INFO"
    return {
        "job_id": job_id,
        "generated_at": now_iso(),
        "model": MODEL,
        "advisory": True,
        "mode": "live" if live else "final",
        "summary": ins[0]["detail"] if ins else "",
        "worst_severity": worst,
        "insights": ins,
    }
