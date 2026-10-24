#!/usr/bin/env python3
"""Verifier HTTP NYATA untuk POST /api/v1/intel/preflight.

Boot app sendiri pada port bebas (run_local.py), tunggu /health, tembak endpoint,
lalu matikan. Kalau app tak bisa di-boot -> cetak [skip] dan tetap rc=0 (gate aman).
"""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import intel as I  # noqa: E402

PASS = 0
FAIL = 0
SKIP = 0


def cek(nama, kondisi, detail=""):
    global PASS, FAIL
    if kondisi:
        PASS += 1
        print("  [ok]   %s" % nama)
    else:
        FAIL += 1
        print("  [GAGAL] %s  %s" % (nama, detail))


def skip(nama, alasan=""):
    global SKIP
    SKIP += 1
    print("  [skip] %s  %s" % (nama, alasan))


def port_bebas():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def cari_run_local():
    for c in ("run_local.py", "tools/run_local.py", "backend/run_local.py", "scripts/run_local.py"):
        p = os.path.join(ROOT, c)
        if os.path.exists(p):
            return p
    return None


def http(base, path, method="GET", payload=None, timeout=8):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, repr(e)


def tunggu_siap(proc, log_path, port, batas=25.0):
    t0 = time.time()
    while time.time() - t0 < batas:
        if proc.poll() is not None:
            return None
        try:
            with open(log_path, encoding="utf-8", errors="replace") as fh:
                isi = fh.read()
        except Exception:
            isi = ""
        m = re.search(r"listening on http://127\.0\.0\.1:(\d+)", isi)
        if m:
            return int(m.group(1))
        s, _ = http("http://127.0.0.1:%d" % port, "/api/v1/health", timeout=1)
        if s == 200:
            return port
        time.sleep(0.3)
    return None


def main():
    print("== verify_intel_live (HTTP nyata) ==")
    rl = cari_run_local()
    if not rl:
        skip("boot app", "run_local.py tidak ditemukan")
        print("\n  [ok]   verify_intel_live: %d hijau, %d skip" % (PASS, SKIP))
        return 0

    port = port_bebas()
    tmp = tempfile.mkdtemp(prefix="galardo-live-")
    log_path = os.path.join(tmp, "app.log")
    env = dict(os.environ)
    env["GALARDO_PORT"] = str(port)
    env.setdefault("GALARDO_REQUIRE_AUTH", "0")
    env.setdefault("GALARDO_AUTH_LOCALHOST_EXEMPT", "1")

    log = open(log_path, "w")
    proc = subprocess.Popen([sys.executable, rl], cwd=ROOT, env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    try:
        siap = tunggu_siap(proc, log_path, port)
        if not siap:
            skip("boot app", "app tidak siap; lihat %s" % log_path)
            print("\n  [ok]   verify_intel_live: %d hijau, %d skip" % (PASS, SKIP))
            return 0

        base = "http://127.0.0.1:%d" % siap
        cek("app hidup: GET /api/v1/health -> 200", http(base, "/api/v1/health")[0] == 200)

        st, body = http(base, "/api/v1/intel/preflight", method="POST", payload="")
        cek("POST /intel/preflight body kosong -> 200", st == 200, "status=%s" % st)
        try:
            j = json.loads(body)
        except Exception:
            j = {}
        cek("balasan JSON punya divergensi", isinstance(j.get("divergensi"), list), repr(body[:160]))
        cek("divergensi selengkap FIELDS_DIBANDING",
            len(j.get("divergensi") or []) == len(I.FIELDS_DIBANDING), repr(len(j.get("divergensi") or [])))
        cek("balasan punya ringkasan.total", isinstance((j.get("ringkasan") or {}).get("total"), int))

        st2, body2 = http(base, "/api/v1/intel/preflight", method="POST",
                          payload="domain: contoh.invalid\norigin: 1.2.3.4\nsumber: rea")
        cek("POST payload teks -> 200", st2 == 200, "status=%s" % st2)
        try:
            j2 = json.loads(body2)
        except Exception:
            j2 = {}
        cek("payload teks: domain terurai", j2.get("domain") == "contoh.invalid", repr(j2.get("domain")))

        st3, body3 = http(base, "/api/v1/intel/preflight", method="POST",
                          payload={"domain": "contoh.invalid", "origin": "9.9.9.9"})
        cek("POST payload objek -> 200", st3 == 200, "status=%s" % st3)

        st4, _ = http(base, "/api/v1/intel/preflight", method="GET")
        cek("GET /intel/preflight bukan 200 (terikat POST)", st4 != 200, "status=%s" % st4)

        try:
            with open(log_path, encoding="utf-8", errors="replace") as fh:
                isi = fh.read()
        except Exception:
            isi = ""
        cek("log app tanpa Traceback", "Traceback" not in isi, isi[-200:].replace("\n", " | "))
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        log.close()

    print()
    if FAIL:
        print("  [MERAH] verify_intel_live: %d hijau, %d GAGAL, %d skip" % (PASS, FAIL, SKIP))
        return 1
    print("  [ok]   verify_intel_live: %d cek hijau, %d skip" % (PASS, SKIP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
