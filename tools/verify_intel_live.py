#!/usr/bin/env python3
"""Verifier HTTP NYATA untuk POST /api/v1/intel/preflight.

Boot app sendiri dengan pola yang sudah terbukti di verify_auth_users.py:
  sh -c 'cd backend && exec python3 -u run_local.py'
plus varian python3 -u langsung. WAJIB -u / PYTHONUNBUFFERED, kalau tidak baris
'listening on http://127.0.0.1:PORT' tidak ter-flush ke file dan deteksi buta.
Log disimpan PER-PERCOBAAN (.out/intel-live-app-<n>.log) supaya bukti tidak saling menimpa.
"""
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".out")
sys.path.insert(0, os.path.join(ROOT, "backend"))

import intel as I  # noqa: E402

RE_LISTEN = re.compile(r"listening on https?://(?:127\.0\.0\.1|localhost):(\d+)")

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


def sehat(port, timeout=1):
    return http("http://127.0.0.1:%d" % port, "/api/v1/health", timeout=timeout)[0] == 200


def tail_of(path, n=12):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            baris = fh.read().splitlines()
    except Exception:
        return "      (log kosong)"
    return "\n".join("      | " + b for b in baris[-n:]) or "      (log kosong)"


def tunggu_siap(proc, logpath, batas=45.0):
    t0 = time.time()
    while time.time() - t0 < batas:
        if proc.poll() is not None:
            return None
        try:
            with open(logpath, encoding="utf-8", errors="replace") as fh:
                isi = fh.read()
        except Exception:
            isi = ""
        m = RE_LISTEN.search(isi)
        if m:
            p = int(m.group(1))
            for _ in range(24):
                if sehat(p):
                    return p
                time.sleep(0.25)
            return p
        time.sleep(0.25)
    return None


def matikan(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=6)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def kandidat_boot():
    py = sys.executable
    rl = os.path.join(ROOT, "backend", "run_local.py")
    out = []
    if os.path.exists(rl):
        out.append((["sh", "-c", "cd backend && exec python3 -u run_local.py"], ROOT))
        out.append(([py, "-u", rl], ROOT))
        out.append(([py, "-u", "run_local.py"], os.path.join(ROOT, "backend")))
    return out


def boot():
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("GALARDO_REQUIRE_AUTH", "0")
    env.setdefault("GALARDO_AUTH_LOCALHOST_EXEMPT", "1")
    logs = []
    for i, (cmd, cwd) in enumerate(kandidat_boot(), 1):
        lp = os.path.join(OUT, "intel-live-app-%d.log" % i)
        logs.append(lp)
        print("    coba %d: %s   (cwd=%s)" % (i, " ".join(cmd), cwd))
        log = open(lp, "w")
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
        siap = tunggu_siap(proc, lp)
        log.close()
        if siap:
            print("    -> SIAP di port %d (log: %s)" % (siap, lp))
            return proc, siap, cmd, lp
        print("      gagal; tail log:")
        print(tail_of(lp, 10))
        matikan(proc)
        time.sleep(0.4)
    return None, None, None, logs


def main():
    print("== verify_intel_live (HTTP nyata) ==")
    if not os.path.isdir(OUT):
        os.makedirs(OUT, exist_ok=True)
    proc, siap, cmd, lp = boot()
    if not siap:
        skip("boot app", "semua strategi gagal")
        print("\n  [skip] verify_intel_live: %d hijau, %d skip (BELUM teruji HTTP)" % (PASS, SKIP))
        return 0

    base = "http://127.0.0.1:%d" % siap
    try:
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

        st3, _ = http(base, "/api/v1/intel/preflight", method="POST",
                      payload={"domain": "contoh.invalid", "origin": "9.9.9.9"})
        cek("POST payload objek -> 200", st3 == 200, "status=%s" % st3)

        st4, _ = http(base, "/api/v1/intel/preflight", method="GET")
        cek("GET /intel/preflight bukan 200 (terikat POST)", st4 != 200, "status=%s" % st4)

        try:
            with open(lp, encoding="utf-8", errors="replace") as fh:
                isi = fh.read()
        except Exception:
            isi = ""
        cek("log app tanpa Traceback", "Traceback" not in isi, isi[-200:].replace("\n", " | "))
    finally:
        matikan(proc)
        try:
            shutil.copyfile(lp, os.path.join(OUT, "intel-live-app.log"))
        except Exception:
            pass

    print()
    if FAIL:
        print("  [MERAH] verify_intel_live: %d hijau, %d GAGAL, %d skip" % (PASS, FAIL, SKIP))
        return 1
    print("  [ok]   verify_intel_live: %d cek hijau, %d skip" % (PASS, SKIP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
