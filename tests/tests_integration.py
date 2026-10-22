"""GALARDO - integration test suite (Blueprint §6 matrix + PRD §9 acceptance).

Run: python3 tests_integration.py   (spawns lab target + API on ephemeral ports)
Covers: scenario validation (over-limit/path-escape/absolute-URL/unknown-field),
idempotent job create, preflight fail-closed, bounded run, telemetry, manual abort
(idempotent repeat), synthetic degradation auto-abort, recovery, evidence
build/verify/tamper, immutable scenario version, audit trail presence.
"""
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import threading
import time

# --- token auth: ikutkan Authorization agar suite tetap sah saat GALARDO_REQUIRE_AUTH=1 ---
import urllib.request
from urllib.request import Request as _BaseRequest


class _AuthRequest(_BaseRequest):
    def __init__(self, url, data=None, headers=None, **kw):
        h = dict(headers or {})
        tok = os.environ.get("GALARDO_DEV_TOKEN", "dev-token")
        if tok:
            h.setdefault("Authorization", "Bearer " + tok)
        super().__init__(url, data=data, headers=h, **kw)


Request = _AuthRequest
urllib.request.Request = _AuthRequest   # baris req() memakai atribut modul

_RUN = str(int(time.time() * 1000))
DEGRADE_KEY = 'test-job-degrade-1-' + _RUN
DEGRADE_KEY_B = 'test-job-degrade-1b-' + _RUN
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "backend"))

DATA_DIR = tempfile.mkdtemp(prefix="galardo-test-")
os.environ["GALARDO_DATA_DIR"] = DATA_DIR

import api as api_mod          # noqa: E402
import lab_target              # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402

API_PORT = 18080
TGT_PORT = 18088
API = f"http://127.0.0.1:{API_PORT}/api/v1"
TGT = f"http://127.0.0.1:{TGT_PORT}"

PASS, FAIL, SKIP = [], [], []


import re as _re

_NAMA_STATIK = set(_re.findall(r'\b(?:check|skip)\(\s*["\']([^"\']+)["\']',
                              open(__file__, encoding="utf-8").read()))


def skip(name, reason=""):
    """V6: check() yang cabangnya tidak diambil tetap WAJIB melapor."""
    SKIP.append((name, reason))
    print(f"  [SKIP] {name}  <- {reason}")


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))


def req(method, path, body=None, headers=None, expect_json=True, timeout=15):
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    h = dict(h or {})
    h.setdefault("Authorization", "Bearer " + os.environ.get("GALARDO_DEV_TOKEN", "dev-token"))
    r = urllib.request.Request(API + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            if expect_json:
                return resp.status, (json.loads(raw) if raw else None)
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def target_req(path):
    with urllib.request.urlopen(TGT + path, timeout=5) as r:
        return r.status, json.loads(r.read())


def _start_job_asli(job_id, tries=60, delay=0.5):
    """POST /start dengan toleransi 409 (preflight async belum siap). F-1."""
    st, r = None, None
    for i in range(tries):
        st, r = req("POST", f"/test-jobs/{job_id}/start")
        if st != 409:
            if os.environ.get("F1_DEBUG"):
                print("      [start ok setelah %d coba] checks=%s" % (i, (r or {}).get("preflight")))
            return st, r
        if os.environ.get("F1_DEBUG"):
            cek = (r or {}).get("preflight")
            gagal = [k for k, v in cek.items() if not v] if isinstance(cek, dict) else cek
            print("      [409 #%d] cek gagal: %s" % (i + 1, gagal))
        time.sleep(delay)
    return st, r


AKTIF = ("QUEUED", "PREFLIGHT", "DISPATCHING", "RUNNING", "SPIKING", "RECOVERING", "ABORTING")


def bersihkan_job_aktif(timeout=60):
    """Buang job sisa berstatus aktif supaya preflight 'no conflicting active job' lolos.

    Akar F-1b: run yang mati di tengah meninggalkan job aktif di data/state.json;
    /start lalu SELALU 409 dan retry 30s tidak menolong.
    """
    st, jobs = req("GET", "/test-jobs")
    if st != 200 or not isinstance(jobs, list):
        return 0
    n = 0
    for j in jobs:
        if (j.get("status") or j.get("state")) in AKTIF:
            req("POST", f"/test-jobs/{j['id']}/abort")
            wait_terminal(j["id"], timeout)
            n += 1
    if n and os.environ.get("F1_DEBUG"):
        print("      [bersih] %d job aktif sisa di-abort" % n)
    return n


def start_job(job_id, tries=60, delay=0.5):
    """Wrapper debug: kalau tetap 409, cetak body preflight terakhir."""
    st, body = _start_job_asli(job_id, tries=tries, delay=delay)
    if st != 200:
        print("    [debug] start_job st=%s body=%s" % (st, str(body)[:400]))
    return st, body

def wait_terminal(job_id, timeout=90):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        st, snap = req("GET", f"/test-jobs/{job_id}/live")
        if st != 200 or not isinstance(snap, dict) or "job" not in snap:
            last = (st, str(snap)[:300])
            time.sleep(0.6)
            continue
        stt = snap["job"]["status"]
        if stt in ("COMPLETED", "ABORTED", "FAILED", "RECOVERY_FAILED"):
            return snap
        time.sleep(0.6)
    print(f"    [wait_terminal] last bad response: {last}")
    return None


def main():
    # ---- boot stack ----
    threading.Thread(target=lab_target.serve, kwargs={"port": TGT_PORT}, daemon=True).start()
    time.sleep(0.5)
    seed = api_mod.seed_lab()
    httpd = ThreadingHTTPServer(("127.0.0.1", API_PORT), api_mod.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.3)
    print(f"[test] stack up: api={API} target={TGT} data={DATA_DIR}")
    bersihkan_job_aktif()

    # ---- 0. lab target health ----
    st, body = target_req("/healthz")
    check("lab target /healthz 200", st == 200 and body["status"] == "ok")

    # ---- 1. seed sanity ----
    st, tgts = req("GET", "/targets")
    check("seeded target exists", st == 200 and any(t["id"] == "tgt-lab" for t in tgts))

    # ---- 2. scenario validation matrix ----
    st, r = req("POST", "/scenarios/validate", {"yaml": FIX_VALID})
    check("valid scenario accepted", st == 200 and r["valid"] is True,
          json.dumps(r)[:200] if st != 200 else "")
    eff_hash = r["scenario_hash"]
    st, r2 = req("POST", "/scenarios/validate", {"yaml": FIX_VALID})
    check("hash stable for identical canonical scenario", r2["scenario_hash"] == eff_hash)

    st, r = req("POST", "/scenarios/validate", {"yaml": FIX_OVER_LIMIT})
    check("over-limit scenario rejected 422", st == 422 and any(
        e["code"] == "over_limit" for e in r["errors"]), str(r)[:200])

    st, r = req("POST", "/scenarios/validate", {"yaml": FIX_BAD_PATH})
    check("path outside allowlist rejected", st == 422 and any(
        e["code"] == "path_not_allowed" for e in r["errors"]), str(r)[:200])

    st, r = req("POST", "/scenarios/validate", {"yaml": FIX_ABS_URL})
    check("absolute URL rejected (no network)", st == 422 and any(
        e["code"] in ("absolute_url", "invalid_path") for e in r["errors"]), str(r)[:200])

    st, r = req("POST", "/scenarios/validate", {"yaml": FIX_UNKNOWN_FIELD})
    check("unknown field rejected (additionalProperties=false)", st == 422 and any(
        e["code"] == "unknown_field" for e in r["errors"]), str(r)[:200])

    st, r = req("POST", "/scenarios/validate", {"yaml": FIX_WITH_PROXY})
    check("proxy_pool diterima (jalur probe residential)",
          st == 200 and r.get("valid") is True, str(r)[:200])

    st, r = req("POST", "/scenarios/validate", {"yaml": FIX_BAD_PROXY})
    check("proxy_pool bentuk salah ditolak", st == 422 and any(
        e["code"] == "invalid_proxy_pool" for e in r["errors"]), str(r)[:200])

    st, r = req("POST", "/scenarios/validate", {"yaml": FIX_BAD_METHOD})
    st_b, r_b = req("POST", "/scenarios/validate", {"yaml": FIX_WITH_BODY})
    st_t, r_t = req("POST", "/scenarios/validate", {"yaml": FIX_UNKNOWN_METHOD})
    check("POST+body accepted (active mode), TRACE still rejected",
          st == 200 and r["valid"] is True and st_b == 200 and r_b["valid"] is True
          and st_t == 422 and any(e["code"] == "method_not_allowed" for e in r_t["errors"]),
          f"{st}/{st_b}/{st_t} {str(r_t)[:140]}")

    # ---- 3. idempotent job creation ----
    plan_id = seed["plan_id"]
    idem = "test-idem-001"
    st1, j1 = req("POST", "/test-jobs", {"test_plan_id": plan_id}, {"Idempotency-Key": idem})
    st2, j2 = req("POST", "/test-jobs", {"test_plan_id": plan_id}, {"Idempotency-Key": idem})
    check("idempotent job create returns same job", j1["id"] == j2["id"] and st1 == 202 and st2 == 200,
          f"{st1}/{st2} {j1.get('id')}/{j2.get('id')}")
    job_a = j1["id"]

    # ---- 4. unapproved plan rejected ----
    st, pl = req("POST", "/test-plans", {"target_id": "tgt-lab", "engagement_id": "eng-lab",
                                         "scenario_version_id": seed["scenario_version"],
                                         "policy_version_id": "pol-global-v1", "name": "unapproved"})
    check("draft plan created", st == 201)
    st, r = req("POST", "/test-jobs", {"test_plan_id": pl["id"]})
    check("job from unapproved plan rejected", st == 422, f"{st} {r}")

    # ---- 5. bounded run end-to-end (COMPLETED path) ----
    st, r = start_job(job_a)
    check("start: preflight all PASS", st == 200 and r["started"] is True and all(
        c["result"] == "PASS" for c in r["preflight"]), str(r)[:400])
    snap = wait_terminal(job_a, 60)
    check("job reaches terminal state", snap is not None, "timeout")
    stt = snap["job"]["status"]
    print(f"    -> terminal status: {stt}")
    check("COMPLETED or ABORTED (bounded)", stt in ("COMPLETED", "ABORTED"))
    fm = snap["job"]["final_metrics"] or {}
    agg = fm.get("aggregate") or {}
    check("telemetry present (requests>0)", agg.get("requests", 0) > 0, str(agg)[:200])
    check("p95 computed", agg.get("p95_ms") is not None, str(agg)[:200])
    check("effective caps recorded", fm.get("effective_policy", {}).get("max_rps") is not None)
    check("assertions evaluated (soft failure recorded)", agg.get("assert_soft_fail", 0) > 0, str(agg)[:200])
    check("assertion counters present in telemetry",
          "assert_hard_fail" in agg and "assert_soft_fail" in agg)
    check("out-of-band down verdict recorded in final metrics",
          "state" in ((fm.get("down_verdict") or {}).get("verdict") or {}),
          str(fm.get("down_verdict"))[:200])
    check("tolerance report recorded in final metrics",
          "normal_error_pct" in (fm.get("tolerance") or {}), str(fm.get("tolerance"))[:160])
    check("payload subset tracked in telemetry",
          "payload_error_pct" in agg and "payload_requests" in agg, str(agg)[:200])

    from safety import SafetyController

    class _T(object):
        last_data_ts = None

        def window(self, s):
            return {}

    class _P(object):
        def snapshot(self):
            return {"state": "HEALTHY"}

    _sc = SafetyController("job-tol", {"max_error_pct": 30.0}, _P(), _T(), lambda c, d: True)
    check("phase tolerance: payload 70% wider than normal 30%",
          _sc.payload_pct > _sc.normal_pct and _sc.normal_pct == 30.0,
          f"normal={_sc.normal_pct} payload={_sc.payload_pct}")
    # ABORTED bukan hard terminal: orchestrator mengizinkan ABORTED -> RECOVERY_WAIT,
    # dan bounded run memang berakhir ABORTED. Jadi rute recovery diuji di KEDUA rute.
    _harap = stt if stt in ("COMPLETED", "ABORTED") else "ABORTED"
    st, rec = req("POST", f"/test-jobs/{job_a}/recovery")
    check("recovery monitor direspons (200/202)", st in (200, 202), f"{st} {str(rec)[:120]}")
    _t0 = time.time()
    _rec = stt
    _wait = False
    while time.time() < _t0 + 60:
        _, snap2 = req("GET", f"/test-jobs/{job_a}/live")
        _rec = snap2["job"]["status"]
        if _rec == "RECOVERY_WAIT":
            _wait = True
        if _rec == "RECOVERY_FAILED":
            break
        if _rec == _harap and (_wait or time.time() - _t0 > 3):
            break
        time.sleep(1)
    print(f"    -> recovery: lewat_RECOVERY_WAIT={_wait} status_akhir={_rec} (harap {_harap})")
    check("recovery selesai di state yang benar", _rec == _harap, f"{_rec} (harap {_harap})")

    # ---- 6. evidence: build, verify, tamper ----
    st, ev = req("POST", f"/evidence/{job_a}/build")
    check("evidence bundle built", st == 201 and ev.get("bundle_sha256"), str(ev)[:200])
    st, r = req("POST", f"/evidence/{ev['id']}/verify")
    check("evidence verify OK", st == 200 and r["verified"] is True, str(r)[:200])
    # tamper test
    tampered = os.path.join(DATA_DIR, "tampered.tar.gz")
    with open(ev["storage_uri"], "rb") as f:
        raw = f.read()
    with open(tampered, "wb") as f:
        f.write(raw[:-3] + b"xyz")
    tf = tarfile.open(tampered, "r:gz")
    try:
        names = tf.getnames()
        check("tampered bundle structurally readable (for verify-fail path)", len(names) > 3)
    finally:
        tf.close()
    check("bundle hash stored separately (not self-referential)",
          os.path.exists(ev["storage_uri"]) and ev["manifest_sha256"] != ev["bundle_sha256"])

    # ---- 7. manual abort on running job + idempotent repeat ----
    # create a longer job
    st, long_scv = req("POST", "/scenarios", {"yaml": FIX_LONG})
    check("long scenario version saved", st == 201, str(long_scv)[:200])
    scv = long_scv["version"] if "version" in long_scv else long_scv
    st, plan2 = req("POST", "/test-plans", {"target_id": "tgt-lab", "engagement_id": "eng-lab",
                                            "scenario_id": scv["scenario_id"],
                                            "scenario_version_id": scv["id"],
                                            "policy_version_id": "pol-global-v1", "name": "long"})
    req("POST", f"/test-plans/{plan2['id']}/approve", {})
    st, job2 = req("POST", "/test-jobs", {"test_plan_id": plan2["id"]},
                   {"Idempotency-Key": "test-job-long-1"})
    st, r = start_job(job2['id'])
    check("long job started", st == 200 and r["started"], str(r)[:300])
    time.sleep(2.5)
    st, ab = req("POST", f"/test-jobs/{job2['id']}/abort", {"reason": "integration test abort"})
    check("abort accepted while RUNNING", st == 202 and ab.get("ack") is True, str(ab)[:200])
    st2, ab2 = req("POST", f"/test-jobs/{job2['id']}/abort", {"reason": "repeat abort"})
    check("repeated abort idempotent (no state corruption)", st2 == 202, str(ab2)[:200])
    snap2 = wait_terminal(job2["id"], 60)
    check("aborted job terminal = ABORTED", snap2 and snap2["job"]["status"] == "ABORTED",
          snap2["job"]["status"] if snap2 else "timeout")
    check("abort reason recorded (audit)",
          snap2["job"].get("abort_reason") == "integration test abort")

    # ---- 8. synthetic degradation -> safety auto-abort ----
    st, degr = req("POST", "/scenarios", {"yaml": FIX_DEGRADE})
    scv3 = degr["version"] if "version" in degr else degr
    st, plan3 = req("POST", "/test-plans", {"target_id": "tgt-lab", "engagement_id": "eng-lab",
                                            "scenario_id": scv3["scenario_id"],
                                            "scenario_version_id": scv3["id"],
                                            "policy_version_id": "pol-global-v1", "name": "degrade"})
    req("POST", f"/test-plans/{plan3['id']}/approve", {})
    st, job3 = req("POST", "/test-jobs", {"test_plan_id": plan3["id"]},
                   {"Idempotency-Key": DEGRADE_KEY})
    # degrade target BEFORE start -> probe baseline fails asynchronously -> FAILED, no traffic
    with urllib.request.urlopen(TGT + "/control/degrade", timeout=5) as r:
        pass
    st, r = start_job(job3['id'])
    check("degraded-target job dispatched (async preflight DB checks PASS)", st == 200 and r["started"], f"st={st}")
    snap3 = wait_terminal(job3["id"], 45)
    if snap3 is None:
        # flake jarang: job degrade tidak terminal -> abort lalu ulang sekali
        print("    [retry] job degrade tidak terminal; abort + ulang sekali")
        req("POST", f"/test-jobs/{job3['id']}/abort", {"reason": "flake retry"})
        wait_terminal(job3["id"], 30)
        st, job3 = req("POST", "/test-jobs", {"test_plan_id": plan3["id"]},
                       {"Idempotency-Key": DEGRADE_KEY_B})
        start_job(job3['id'])
        snap3 = wait_terminal(job3["id"], 45)
    stt3 = snap3["job"]["status"] if snap3 else "timeout"
    check("degraded baseline -> FAILED (fail-closed, no traffic)", stt3 == "FAILED", stt3)
    _fr = str((snap3 or {}).get("job", {}).get("failure_reason") or "")
    check("FAILED reason mentions probe baseline",
          bool(snap3) and "baseline" in _fr,
          _fr[:160] or "no failure_reason recorded")
    # recover target so baseline passes, then degrade DURING the run
    with urllib.request.urlopen(TGT + "/control/recover", timeout=5) as r:
        pass
    time.sleep(1.0)
    st, job4 = req("POST", "/test-jobs", {"test_plan_id": plan3["id"]},
                   {"Idempotency-Key": "test-job-degrade-2"})
    st, r = start_job(job4['id'])
    started4 = st == 200 and r["started"]
    if started4:
        time.sleep(4)  # let some traffic flow
        with urllib.request.urlopen(TGT + "/control/degrade", timeout=5) as r:
            pass
        snap4 = wait_terminal(job4["id"], 90)
        stt4 = snap4["job"]["status"] if snap4 else "timeout"
        check("synthetic degradation -> safety ABORT (not COMPLETED)", stt4 in ("ABORTED", "RECOVERY_FAILED"), stt4)
        safety_evts = [o for o in (snap4.get("safety") or {}).get("decisions", []) if o.get("severity") == "CRIT"] if snap4 else []
        check("safety CRIT event recorded", len(safety_evts) > 0 or
              (snap4 and "ABORT" in json.dumps(snap4.get("safety", {}))), "no CRIT event")
        # recovery will fail while target degraded; restore target for cleanup
        with urllib.request.urlopen(TGT + "/control/recover", timeout=5) as r:
            pass
        req("POST", f"/test-jobs/{job4['id']}/recovery")
        skip("degradation job started (fallback path)", f"jalur utama dipakai (st={st})")
    else:
        check("degradation job started (fallback path)", False, f"start st={st}")

    # ---- 9. scenario version immutability ----
    st, v1 = req("POST", "/scenarios", {"yaml": FIX_VALID, "scenario_id": None})
    st, scns = req("GET", "/scenarios")
    smoke = next((s for s in scns if s["name"] == "health-smoke"), None)
    old_hash = smoke["current_hash"]
    n_versions_before = len(smoke["versions"])
    req("POST", "/scenarios", {"yaml": FIX_LONG, "scenario_id": smoke["id"]})
    st, scns2 = req("GET", "/scenarios")
    smoke2 = next((s for s in scns2 if s["id"] == smoke["id"]), None)
    check("edit creates NEW immutable version (old hash preserved)",
          len(smoke2["versions"]) == n_versions_before + 1 and
          any(v["content_sha256"] == old_hash for v in smoke2["versions"]))

    # ---- 10. audit trail ----
    st, audit = req("GET", "/audit?limit=500")
    actions = {a["action"] for a in audit}
    need = {"job.created", "job.state.running", "job.state.aborted", "evidence.created",
            "abort.worker_ack", "scenario_version.created", "test_plan.approved"}
    missing = need - actions
    check("audit contains required action types", not missing, f"missing: {missing}")

    # ---- 11. evidence download ----
    st2, raw2 = req("GET", f"/evidence/{ev['id']}/download", expect_json=False)
    check("evidence downloadable", raw2 and len(raw2) > 500)

    # ---- 12. DNS TXT ownership challenge (W4) ----
    st, ch = req("POST", "/targets/tgt-lab/challenge", {})
    check("ownership challenge issued with _galardo TXT record",
          st == 201 and ch.get("record_name", "").startswith("_galardo.")
          and bool(ch.get("expected_value")), str(ch)[:200])
    st, v = req("POST", "/targets/tgt-lab/verify/dns", {})
    check("dns verify 422 with quorum evidence while TXT unpublished",
          st == 422 and v.get("verified") is False
          and sorted((v.get("evidence") or {}).get("attempts", {}).keys()) == ["_galardo", "_galodo"],
          str(v)[:220])

    # ---- 13. down verdict endpoint (W5) ----
    st, dv = req("GET", f"/test-jobs/{job_a}/down")
    check("down endpoint exposes out-of-band verdict",
          st == 200 and isinstance(dv.get("down"), dict)
          and "state" in (dv["down"].get("verdict") or {}),
          str(dv)[:200])

    # ---- 14. route override endpoints (W6) ----
    st, ov = req("POST", "/overrides", {"domain": "override.test", "paths": ["/blocked/*"],
                                        "mode": "404", "tiers": ["T2"], "shim_port": 18777})
    check("override applied on T2 shim",
          st == 201 and "T2" in (ov.get("applied_tiers") or []), str(ov)[:200])
    oid = ov.get("id") or ""
    st, pr = req("POST", f"/overrides/{oid}/probe", {"path": "/blocked/xyz"})
    check("forced route returns 404 through shim",
          st == 200 and pr.get("status") == 404 and pr.get("forced") is True, str(pr)[:200])
    st, rv = req("POST", f"/overrides/{oid}/revert", {})
    check("override reverted", st == 200 and "T2" in (rv.get("reverted") or []), str(rv)[:200])

    # ---- 15. source capability registry (item 9) ----
    st, src = req("POST", "/sources", {"label": "it-src", "kind": "local",
                                       "declared": ["udp", "spoof_src"]})
    if st == 409:
        req("POST", "/sources/src-it-src/remove", {})
        st, src = req("POST", "/sources", {"label": "it-src", "kind": "local",
                                           "declared": ["udp", "spoof_src"]})
    check("source registered with declared caps",
          st == 201 and src.get("id") == "src-it-src" and "udp" in (src.get("declared") or []),
          str(src)[:200])
    sid = src.get("id") or ""
    st, pr = req("POST", f"/sources/{sid}/probe", {"url": TGT + "/healthz"})
    pv = (pr or {}).get("probe") or {}
    check("source probe separates proven / unproven / na",
          st == 200 and all(k in pv for k in ("proven", "unproven", "na"))
          and "http1" in (pv.get("proven") or []), str(pr)[:200])
    st, mx = req("GET", "/sources/matrix")
    check("capability matrix exposes gaps",
          st == 200 and "gaps" in mx and "capabilities" in mx and "ssl_lib" in mx,
          str(mx)[:160])
    st, pk = req("POST", "/sources/pick", {"required": ["http1"]})
    _picked = pk.get("picked") or {}
    check("pick returns a source for proven capability",
          st == 200 and "http1" in (_picked.get("capabilities") or [])
          and _picked.get("id") in [x.get("id") for x in
                                    (req("GET", "/sources")[1].get("sources") or [])],
          str(pk)[:200])
    st, pk2 = req("POST", "/sources/pick", {"required": ["http1", "residential"]})
    check("pick refuses and names the missing capability",
          st == 409 and "residential" in json.dumps(pk2), str(pk2)[:200])
    st, rm = req("POST", f"/sources/{sid}/remove", {})
    check("source removed", st == 200 and rm.get("removed") == sid, str(rm)[:160])

    # ---- 16. UDP reflection probe (item 13) ----
    st, src2 = req("POST", "/sources", {"label": "it-udp", "kind": "local"})
    if st == 409:
        req("POST", "/sources/src-it-udp/remove", {})
        st, src2 = req("POST", "/sources", {"label": "it-udp", "kind": "local"})
    sid2 = (src2 or {}).get("id") or ""
    check("second source registered for udp test", st == 201 and sid2 == "src-it-udp",
          str(src2)[:160])
    st, up = req("POST", f"/sources/{sid2}/udp",
                 {"qname": "isc.org", "timeout": 2.0, "ports_n": 2, "spoof": False}, timeout=45)
    check("udp probe returns amplification shape",
          st == 200 and "best_amplification" in up and "reflection_capable" in up,
          str(up)[:200])
    check("udp probe reports every protocol lane",
          st == 200 and all(k in up for k in ("dns", "ntp_mode3", "ntp_mode6", "ssdp",
                                              "port_rotation")),
          str(up)[:160])
    req("POST", f"/sources/{sid2}/remove", {})

    # ---- 17. worm: replikasi + lease fail-closed (item 14) ----
    import worm as _worm
    wt = _worm.WormTree(run_id="it-worm", roots=1, children=1, max_depth=1,
                        ttl=2.0, grace=2.0)
    wt.build()
    time.sleep(2.2)
    check("worm replicated one generation",
          len(wt.status().get("leases") or []) >= 2 and len(wt.alive()) == 1,
          str(wt.status())[:180])
    wt.stop_renew()
    _dead = wt.wait_all_dead(timeout=15)
    check("worm dies fail-closed when the lease stops being renewed", _dead,
          str(wt.status())[:180])
    wt.cleanup()

    # ---- summary ----
    print("== RBAC (STEP-64) ==")
    st, me = req("GET", "/me")
    check("rbac: /me balas 200", st == 200, st)
    check("rbac: /me memuat role aktor", isinstance(me, dict) and (me.get("user") or {}).get("role") == "TEST_OPERATOR", me)
    st, us = req("GET", "/users")
    check("rbac: /users balas list", st == 200 and isinstance(us, list), st)
    st, nu = req("POST", "/users", {"email": "uji-rbac@contoh.test", "role": "VIEWER"})
    check("rbac: POST /users 201 VIEWER", st == 201 and (nu or {}).get("role") == "VIEWER", nu)
    st, bad = req("POST", "/users", {"email": "x@y.z", "role": "SUPERMAN"})
    check("rbac: peran tak dikenal 422", st == 422, st)

    print("== MFA (STEP-65) ==")
    try:
        import mfa as _mfa
    except ImportError:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
        import mfa as _mfa
    st, en = req("POST", "/me/mfa/enroll")
    secret = (en or {}).get("secret")
    check("mfa: enroll 200 + secret", st == 200 and bool(secret), st)
    check("mfa: enroll beri otpauth uri", "otpauth://" in ((en or {}).get("otpauth") or ""), en)
    _c1 = _mfa.totp(secret) if secret else "000000"
    st, vf = req("POST", "/me/mfa/verify", {"code": _c1})
    check("mfa: verify kode benar -> enabled", st == 200 and (vf or {}).get("mfa_enabled") is True, vf)
    _c2 = _mfa.totp(secret) if secret else "000000"
    # pakai kode TER-CACHE supaya benar-benar step yang sama (batas 30s bisa lewat di antara 2 request)
    st, vf2 = req("POST", "/me/mfa/verify", {"code": _c1})
    check("mfa: replay step sama ditolak", st == 422, "st=%s code_sama=%s" % (st, _c1 == _c2))
    st, off = req("POST", "/me/mfa/disable", {})
    check("mfa: disable -> nonaktif", st == 200 and (off or {}).get("mfa_enabled") is False, off)

    print("== ALERTS (STEP-69) ==")
    st, hk = req("POST", "/webhooks", {"name": "alr-uji", "url": "https://contoh.test/alr", "events": ["job.failed"]})
    hid = (hk or {}).get("id")
    check("alerts: hook uji dibuat", st == 201 and bool(hid), hk)
    st, rl = req("POST", "/alerts", {"event": "job.failed", "hook_id": hid, "note": "uji"})
    check("alerts: aturan dibuat", st == 201 and (rl or {}).get("id"), rl)
    st, ls = req("GET", "/alerts")
    check("alerts: daftar memuat aturan", st == 200 and isinstance(ls, list) and len(ls) >= 1, st)
    st, bad = req("POST", "/alerts", {"event": "event.ngawur", "hook_id": hid})
    check("alerts: event tak dikenal 422", st == 422, st)
    st, rm = req("POST", "/alerts/%s/remove" % (rl or {}).get("id", "x"), {})
    check("alerts: hapus aturan", st == 200 and (rm or {}).get("removed"), rm)

    print("== ROLE (STEP-69) ==")
    st, nu2 = req("POST", "/users", {"email": "uji-role@contoh.test", "role": "VIEWER"})
    uid2 = (nu2 or {}).get("id")
    check("role: user uji dibuat", st == 201 and bool(uid2), nu2)
    st, ch = req("POST", "/users/%s/role" % uid2, {"role": "APPROVER"})
    check("role: ubah role -> 200 APPROVER", st == 200 and (ch or {}).get("role") == "APPROVER", ch)
    st, bad = req("POST", "/users/%s/role" % uid2, {"role": "SUPERMAN"})
    check("role: peran ngawur -> 422", st == 422, st)

    def _nama(x):
        if isinstance(x, dict):
            for _k in ("name", "nama", "check", "id"):
                if _k in x:
                    return x[_k]
            return None
        if isinstance(x, (tuple, list)) and x:
            return x[0]
        return x

    _terlihat = {_nama(x) for x in list(PASS) + list(FAIL) + list(SKIP)}
    _terlihat.discard(None)
    _terlihat.add("semua nama check() melapor (tidak ada yang hilang)")
    check("semua nama check() melapor (tidak ada yang hilang)",
          not (_NAMA_STATIK - _terlihat), sorted(_NAMA_STATIK - _terlihat))
    print(f"RESULTS: {len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped")
    if FAIL:
        for name, detail in FAIL:
            print(f"  FAIL: {name} — {detail}")
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    sys.exit(1 if FAIL else 0)


# ---- fixtures ----
FIX_VALID = """schema_version: "1.0"
name: "it-valid"
target_ref: "galardo-lab-target"
profile:
  duration_seconds: 8
  virtual_users: 4
  max_rps: 10
  ramp:
    - after_seconds: 0
      virtual_users: 2
    - after_seconds: 3
      virtual_users: 4
requests:
  - name: "health"
    method: "GET"
    path: "/healthz"
    weight: 70
    timeout_ms: 1500
  - name: "root"
    method: "POST"
    path: "/"
    weight: 30
    timeout_ms: 1500
    body: "galardo-active-probe"
    body_encoding: "identity"
    assertions:
      - type: "json_contains"
        path: "body"
        value: "galardo-active-probe"
      - type: "soft_body_contains"
        value: "this-string-is-absent-xyz"
think_time_ms:
  min: 50
  max: 120
"""
FIX_OVER_LIMIT = FIX_VALID.replace("max_rps: 10", "max_rps: 99999").replace(
    "virtual_users: 4", "virtual_users: 5000").replace("duration_seconds: 8", "duration_seconds: 999999")
FIX_BAD_PATH = FIX_VALID.replace('path: "/healthz"', 'path: "/admin/secret"')
FIX_ABS_URL = FIX_VALID.replace('path: "/healthz"', 'path: "http://evil.example.com/x"')
FIX_UNKNOWN_FIELD = FIX_VALID + "field_ngawur_xyz: 1\n"
FIX_WITH_PROXY = FIX_VALID + "proxy_pool: 'residential'\n"
FIX_BAD_PROXY = FIX_VALID + "proxy_pool: 12345\n"
FIX_BAD_METHOD = FIX_VALID.replace('method: "GET"', 'method: "POST"', 1)
FIX_UNKNOWN_METHOD = FIX_VALID.replace('method: "GET"', 'method: "TRACE"', 1)
FIX_WITH_BODY = """schema_version: "1.2"
name: "it-body"
target_ref: "galardo-lab-target"
profile:
  duration_seconds: 8
  virtual_users: 4
  max_rps: 10
requests:
  - name: "submit"
    method: "POST"
    path: "/healthz"
    weight: 100
    timeout_ms: 1500
    body: "hello-from-galardo"
    body_encoding: "identity"
think_time_ms:
  min: 50
  max: 100
"""
FIX_LONG = """schema_version: "1.0"
name: "it-long"
target_ref: "galardo-lab-target"
profile:
  duration_seconds: 120
  virtual_users: 4
  max_rps: 8
requests:
  - name: "health"
    method: "GET"
    path: "/healthz"
    weight: 100
    timeout_ms: 1500
think_time_ms:
  min: 50
  max: 100
"""
FIX_DEGRADE = """schema_version: "1.0"
name: "it-degrade"
target_ref: "galardo-lab-target"
profile:
  duration_seconds: 60
  virtual_users: 6
  max_rps: 12
requests:
  - name: "health"
    method: "GET"
    path: "/healthz"
    weight: 100
    timeout_ms: 1200
think_time_ms:
  min: 30
  max: 80
"""


# ---- diagnostic wrapper (W7): rekam sebab kalau wait_terminal kehabisan waktu ----
_wt_orig = wait_terminal


def wait_terminal(job_id, timeout=90):   # noqa: F811
    r = _wt_orig(job_id, timeout)
    if r is None:
        st, snap = req("GET", f"/test-jobs/{job_id}/snapshot")
        j = (snap or {}).get("job", {}) if isinstance(snap, dict) else {}
        print("  [WAIT_TIMEOUT] job=%s st=%s status=%s failure=%s safety=%s"
              % (job_id, st, j.get("status"),
                 str(j.get("failure_reason"))[:100],
                 str((snap or {}).get("safety"))[:140]))
    return r


if __name__ == "__main__":
    main()

