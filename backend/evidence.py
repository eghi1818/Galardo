"""GALARDO - Evidence engine (Technical Design §14, Governance §7).

Builds a tar.gz bundle: manifest.json (per-file SHA-256, byte length, media
type), scenario/policy snapshots, telemetry export, probe series, observations,
safety events, recovery record, redacted logs. Bundle SHA-256 computed AFTER
archive finalization and stored separately in DB + audit (never inside itself).
Path traversal is rejected on member names.
"""
import gzip
import io
import json
import os
import tarfile

import db
from util import now_iso, sha256_bytes, sha256_text, canonical_json


def _member_bytes(name, data, mime):
    if name.startswith("/") or ".." in name or "\\" in name:
        raise ValueError(f"unsafe member path: {name}")
    return {"path": name, "bytes": data, "media_type": mime}


def build_evidence_bundle(job_id, actor="system"):
    job = db.get("test_jobs", job_id)
    if not job:
        return None, "job not found"
    if job.get("evidence_id"):
        ev = db.get("evidence_bundles", job["evidence_id"])
        if ev:
            return ev, "already exists"

    db.update("test_jobs", job_id, lambda j: j.update({"status": j.get("status", "COMPLETED")}),
              audit=False)
    db.audit_event(actor, "evidence.build_started", "test_job", job_id,
                   reason=job.get("abort_reason") or "")

    plan = db.get("test_plans", job.get("test_plan_id") or "")
    scv = db.get("scenario_versions", plan.get("scenario_version_id") or "") if plan else None
    target = db.get("targets", plan.get("target_id") or "") if plan else None
    run = None
    runs = db.list("test_runs", lambda r: r.get("job_id") == job_id)
    if runs:
        run = sorted(runs, key=lambda r: r.get("started_at") or "")[-1]
    policy = db.get("safety_policies", plan.get("policy_version_id") or "") if plan else None
    recovery = db.list("recoveries", lambda r: r.get("job_id") == job_id)
    recovery = recovery[-1] if recovery else None
    observations = db.list("observations", lambda o: o.get("job_id") == job_id)
    observations.sort(key=lambda o: o.get("observed_at") or "")
    safety_events = [o for o in observations if o.get("source") == "safety"]

    members = []

    def add(name, obj, mime="application/json"):
        data = json.dumps(obj, indent=1, default=str).encode("utf-8")
        members.append(_member_bytes(name, data, mime))

    # Immutable snapshots frozen at build time
    add("manifest.refs.json", {
        "job_id": job_id, "generated_at": now_iso(),
        "test_plan_id": plan.get("id") if plan else None,
        "scenario_version_id": scv.get("id") if scv else None,
        "scenario_sha256": scv.get("content_sha256") if scv else None,
        "policy_version_id": policy.get("id") if policy else None,
        "policy_hash": policy.get("policy_sha256") if policy else None,
        "target_id": target.get("id") if target else None,
        "target_origin": target.get("canonical_origin") if target else None,
        "worker_identity": {"kind": "in-process bounded engine", "version": "1.0"},
    })
    if plan:
        add("test_plan.json", plan)
    if scv:
        add("scenario.normalized.json", scv.get("normalized_json"))
        add("scenario.sha256", scv.get("content_sha256"), "text/plain")
    if policy:
        add("safety_policy.json", policy)
    if target:
        add("target_scope.json", {k: target.get(k) for k in (
            "id", "name", "environment", "canonical_origin", "allowed_paths",
            "probe_contract", "status", "valid_from", "valid_until")})
    telemetry_export = job.get("final_metrics") or {}
    add("telemetry/metrics.json", telemetry_export)
    if run and run.get("probe_series"):
        add("telemetry/probe.json", run.get("probe_series"))
    add("observations.json", observations)
    add("safety_events.json", safety_events)
    if run:
        add("timeline.jsonl", {"lines": run.get("timeline") or []})
    if recovery:
        add("recovery.json", recovery)
    add("application_logs_redacted.jsonl", {
        "note": "headers/cookies/tokens redacted by design; scenarios forbid sensitive headers",
        "lines": (job.get("operator_notes") or []),
    })

    # manifest: per-file sha256
    manifest_entries = [{
        "path": m["path"], "byte_length": len(m["bytes"]),
        "media_type": m["media_type"], "sha256": sha256_bytes(m["bytes"]),
    } for m in members]
    manifest = {"created_at": now_iso(), "job_id": job_id,
                "algorithm": "sha256", "files": manifest_entries}
    manifest_bytes = json.dumps(manifest, indent=1).encode("utf-8")

    # Build tar.gz in memory
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for m in members:
            info = tarfile.TarInfo(name=m["path"])
            info.size = len(m["bytes"])
            info.mtime = 0
            tar.addfile(info, io.BytesIO(m["bytes"]))
        minfo = tarfile.TarInfo(name="manifest.json")
        minfo.size = len(manifest_bytes)
        minfo.mtime = 0
        tar.addfile(minfo, io.BytesIO(manifest_bytes))
    bundle_bytes = buf.getvalue()
    bundle_sha = sha256_bytes(bundle_bytes)
    manifest_sha = sha256_bytes(manifest_bytes)

    ev_id = f"evd-{job_id}"
    ev_dir = os.path.join(db.DATA_DIR, "evidence")
    os.makedirs(ev_dir, exist_ok=True)
    ev_path = os.path.join(ev_dir, f"evidence_{job_id}.tar.gz")
    with open(ev_path, "wb") as f:
        f.write(bundle_bytes)

    ev_doc = {
        "id": ev_id, "job_id": job_id,
        "storage_uri": ev_path, "storage_rel": f"data/evidence/evidence_{job_id}.tar.gz",
        "manifest_sha256": manifest_sha, "bundle_sha256": bundle_sha,
        "file_count": len(manifest_entries),
        "byte_size": len(bundle_bytes),
        "created_at": now_iso(), "created_by": actor,
        "status": "VERIFIED",
        "manifest": manifest_entries,
    }
    db.insert("evidence_bundles", ev_doc, actor=actor,
              action="evidence.created", resource_type="evidence_bundle",
              reason=f"bundle_sha256={bundle_sha[:16]} files={len(manifest_entries)}")
    try:
        import webhooks
        webhooks.fire("evidence.created", {"evidence_id": ev_id, "job_id": job_id,
                                           "bundle_sha256": bundle_sha,
                                           "manifest_sha256": manifest_sha,
                                           "file_count": len(manifest_entries),
                                           "byte_size": len(bundle_bytes)})
    except Exception:
        pass
    db.update("test_jobs", job_id, lambda j: j.update({"evidence_id": ev_id}),
              actor=actor, action="evidence.linked", resource_type="test_job",
              reason=f"evidence {ev_id}")
    return ev_doc, "built"


def verify_evidence_bundle(evidence_id, actor="system"):
    """Re-verify every file hash + bundle hash. Returns (ok, detail)."""
    ev = db.get("evidence_bundles", evidence_id)
    if not ev:
        return None, "evidence not found"
    path = ev["storage_uri"]
    if not os.path.exists(path):
        db.update("evidence_bundles", evidence_id, lambda e: e.update({"status": "MISSING"}),
                  actor=actor, action="evidence.verify_failed", reason="bundle file missing")
        return False, "bundle file missing"
    raw = open(path, "rb").read()
    if sha256_bytes(raw) != ev["bundle_sha256"]:
        db.update("evidence_bundles", evidence_id, lambda e: e.update({"status": "FAILED"}),
                  actor=actor, action="evidence.verify_failed", reason="bundle hash mismatch")
        return False, "bundle SHA-256 mismatch (content changed)"
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            names = {m.name for m in tar.getmembers()}
            if "manifest.json" not in names:
                return False, "manifest.json missing from bundle"
            mdata = tar.extractfile("manifest.json").read()
            if sha256_bytes(mdata) != ev["manifest_sha256"]:
                db.update("evidence_bundles", evidence_id, lambda e: e.update({"status": "FAILED"}),
                          actor=actor, action="evidence.verify_failed", reason="manifest hash mismatch")
                return False, "manifest SHA-256 mismatch"
            manifest = json.loads(mdata)
            name_map = {m["path"]: m for m in manifest["files"]}
            for path_name, meta in name_map.items():
                if path_name not in names:
                    db.update("evidence_bundles", evidence_id, lambda e: e.update({"status": "FAILED"}),
                              actor=actor, action="evidence.verify_failed", reason=f"member missing: {path_name}")
                    return False, f"member missing: {path_name}"
                data = tar.extractfile(path_name).read()
                if sha256_bytes(data) != meta["sha256"] or len(data) != meta["byte_length"]:
                    db.update("evidence_bundles", evidence_id, lambda e: e.update({"status": "FAILED"}),
                              actor=actor, action="evidence.verify_failed", reason=f"member hash mismatch: {path_name}")
                    return False, f"member hash mismatch: {path_name}"
    except tarfile.TarError as e:
        return False, f"archive error: {e}"
    db.update("evidence_bundles", evidence_id, lambda e: e.update({
        "status": "SEALED", "verified_at": now_iso(), "verified_by": actor}),
        actor=actor, action="evidence.verified", resource_type="evidence_bundle",
        reason="all file + bundle hashes match")
    return True, f"VERIFIED: {ev['file_count']} files, bundle_sha256={ev['bundle_sha256'][:16]}..."
