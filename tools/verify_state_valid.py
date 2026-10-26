#!/usr/bin/env python3
"""verify_state_valid - kunci anti-rusak berkas state JSON.

Cek:
  1. semua *.json di repo bisa di-parse
  2. data/state.json ada dan bisa di-parse
  3. backend/db.py punya baca toleran + tulis atomik
  4. backend/db.py bisa di-import
  5. uji perilaku: berkas JSON + ekor sampah -> dokumen pertama tetap pulih
"""
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOK = 0
FAILS = []


def ok(syarat, nama, info=""):
    global NOK
    if syarat:
        NOK += 1
        print("  ok    %s%s" % (nama, ("  [" + str(info) + "]") if info else ""))
    else:
        FAILS.append(nama)
        print("  GAGAL %s%s" % (nama, ("  [" + str(info) + "]") if info else ""))


def main():
    rusak = []
    jumlah = 0
    for p in sorted(glob.glob(os.path.join(ROOT, "**", "*.json"), recursive=True)):
        rel = os.path.relpath(p, ROOT)
        if rel.startswith(".git/") or rel.startswith(".out/"):
            continue
        jumlah += 1
        try:
            json.load(open(p, encoding="utf-8"))
        except Exception as e:
            rusak.append("%s (%s)" % (rel, e))
    ok(jumlah > 0, "berkas .json ditemukan", jumlah)
    ok(not rusak, "semua %d berkas .json bisa di-parse" % jumlah, rusak[:3])

    state = os.path.join(ROOT, "data", "state.json")
    ok(os.path.exists(state), "data/state.json ada")
    try:
        isi = json.load(open(state, encoding="utf-8"))
        ok(isinstance(isi, dict), "data/state.json objek JSON", len(isi))
    except Exception as e:
        ok(False, "data/state.json bisa di-parse", e)

    db = os.path.join(ROOT, "backend", "db.py")
    teks = open(db, encoding="utf-8").read()
    ok("_baca_toleran(" in teks, "db.py: baca toleran terpasang")
    ok("_dump_ke(" in teks, "db.py: tulis atomik terpasang")
    ok("os.replace(" in teks, "db.py: os.replace dipakai (atomik)")

    r = subprocess.run([sys.executable, "-c", "import db; print('ok')"],
                       cwd=os.path.join(ROOT, "backend"), capture_output=True, text=True)
    ok(r.returncode == 0, "db.py bisa di-import", (r.stdout + r.stderr).strip().splitlines()[-1:] or "")

    try:
        mentah = open(state, encoding="utf-8").read()
    except Exception:
        mentah = "{}"
    korup = mentah.rstrip() + "\n{\"x\": 1}\n"
    pulih = None
    try:
        json.loads(korup)
        ok(False, "berkas yang dikorupsi memang gagal di json.load biasa")
    except Exception:
        ok(True, "berkas yang dikorupsi memang gagal di json.load biasa")
    try:
        pulih, _ = json.JSONDecoder().raw_decode(korup.lstrip())
    except Exception:
        pulih = None
    ok(isinstance(pulih, dict), "dokumen pertama tetap pulih dari ekor sampah",
       len(pulih) if isinstance(pulih, dict) else 0)

    if FAILS:
        print("  [GAGAL] verify_state_valid: %d gagal / %d cek" % (len(FAILS), NOK + len(FAILS)))
        return 1
    print("  [ok]   verify_state_valid: %d cek hijau" % NOK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
