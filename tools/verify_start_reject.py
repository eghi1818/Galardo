#!/usr/bin/env python3
"""Kunci regresi F-1b: 409 KONFLIK harus retryable (tetap PENDING, bisa distart ulang);
409 cek mandatory lain harus terminal (REJECTED); state PREFLIGHT bisa distart ulang."""
import os, sys, tempfile, pathlib, traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="galardo-vsr-")
for k in ("GALARDO_DATA_DIR", "GALARDO_STATE_DIR", "GALARDO_DB_DIR",
          "GALARDO_HOME", "GALARDO_DATA_PATH", "GALARDO_STATE_PATH"):
    os.environ[k] = TMP
sys.path.insert(0, str(ROOT / "backend"))

OK = FAIL = 0
def cek(nama, syarat, info=""):
    global OK, FAIL
    if syarat: OK += 1; print("  ok    " + nama)
    else: FAIL += 1; print("  GAGAL " + nama + " " + str(info))

import db
import orchestrator as orch
try:
    import api as api_mod
except Exception as e:
    api_mod = None; print("  info: api err:", e)

REAL = orch.run_preflight

def ambil(obj, dalam=0):
    """telusuri tuple/list/dict bersarang sampai ketemu dict ber-'id'."""
    if dalam > 5: return None
    if isinstance(obj, dict):
        if "id" in obj: return obj
        for v in obj.values():
            r = ambil(v, dalam + 1)
            if r: return r
    elif isinstance(obj, (tuple, list)):
        for v in obj:
            r = ambil(v, dalam + 1)
            if r: return r
    return None

pid = None
if api_mod is not None and hasattr(api_mod, "seed_lab"):
    try: api_mod.seed_lab()
    except Exception as e: print("  info: seed_lab err:", e)
try: plans = db.list("test_plans") or []
except Exception: plans = []
if plans:
    pid = plans[0].get("id")
    if plans[0].get("status") != "APPROVED":
        try: db.update("test_plans", pid, lambda p: p.update({"status": "APPROVED"}))
        except Exception: pass
print("  info: plan =", pid)

def buat_job(key):
    r = orch.create_job(pid, "verifier", key)
    j = ambil(r)
    assert j and "id" in j, "create_job tidak balikin job: %r" % (r,)
    return j

def mulai(job_id):
    try: r = orch.start_job(job_id, actor="verifier")
    except TypeError: r = orch.start_job(job_id)
    if isinstance(r, tuple) and len(r) >= 2: return r[0], (r[1] or [])
    return r, []

def status(job_id):
    j = ambil(db.get("test_jobs", job_id))
    return (j or {}).get("status")

KONFLIK = [{"check": "no conflicting active job", "result": "FAIL",
            "reason": "one active job per target", "mandatory": True}]
LAIN    = [{"check": "engagement aktif", "result": "FAIL",
            "reason": "engagement tidak aktif", "mandatory": True}]
LOLOS   = [{"check": "semua", "result": "PASS", "reason": "ok", "mandatory": True}]

print("== kasus 1: konflik -> retryable, tetap PENDING, retry sukses ==")
try:
    orch.run_preflight = lambda jid: list(KONFLIK)
    j1 = buat_job("vsr-konflik")
    ok1, c1 = mulai(j1["id"])
    cek("1a start gagal", ok1 is False)
    cek("1b ditandai retryable", any(c.get("check") == "retryable" and c.get("result") == "YES" for c in c1))
    st = status(j1["id"])
    cek("1c state tetap PENDING", st == "PENDING", "st=" + str(st))
    orch.run_preflight = lambda jid: list(LOLOS)
    ok2, _ = mulai(j1["id"])
    cek("1d retry berhasil", ok2 is True)
except Exception:
    traceback.print_exc(); FAIL += 1

print("== kasus 2: cek mandatory lain -> REJECTED ==")
try:
    orch.run_preflight = lambda jid: list(LAIN)
    j2 = buat_job("vsr-terminal")
    ok3, c3 = mulai(j2["id"])
    cek("2a start gagal", ok3 is False)
    cek("2b tidak retryable", any(c.get("check") == "retryable" and c.get("result") == "NO" for c in c3))
    st2 = status(j2["id"])
    cek("2c state REJECTED", st2 == "REJECTED", "st=" + str(st2))
except Exception:
    traceback.print_exc(); FAIL += 1

print("== kasus 3: state PREFLIGHT bisa distart ulang ==")
try:
    orch.run_preflight = lambda jid: list(LOLOS)
    j3 = buat_job("vsr-preflight")
    try: db.update("test_jobs", j3["id"], lambda x: x.update({"status": "PREFLIGHT"}))
    except Exception: pass
    cek("3a set PREFLIGHT", status(j3["id"]) == "PREFLIGHT", "st=" + str(status(j3["id"])))
    ok4, _ = mulai(j3["id"])
    cek("3b PREFLIGHT startable", ok4 is True)
except Exception:
    traceback.print_exc(); FAIL += 1

orch.run_preflight = REAL
print("VERIFY_START_REJECT: ok=%d gagal=%d" % (OK, FAIL))
sys.exit(1 if FAIL else 0)
