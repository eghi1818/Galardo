#!/usr/bin/env python3
"""Pengunci daftar cek kanonik: docs/VERIFIER-COUNT.md wajib memuat SEMUA tools/verify_*.py."""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "VERIFIER-COUNT.md")
PASS = 0
FAIL = 0


def cek(nama, kondisi, detail=""):
    global PASS, FAIL
    if kondisi:
        PASS += 1
        print("  [ok]   %s" % nama)
    else:
        FAIL += 1
        print("  [GAGAL] %s  %s" % (nama, detail))


def main():
    print("== verify_verifier_count ==")
    verifier = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "tools", "verify_*.py")))
    cek("docs/VERIFIER-COUNT.md ada", os.path.exists(OUT))
    if not os.path.exists(OUT):
        return 1
    isi = open(OUT, encoding="utf-8").read()
    kurang = [v for v in verifier if v not in isi]
    cek("semua verifier tercatat", not kurang, "kurang: %s" % kurang)
    cek("memuat jumlah verifier", "jumlah verifier:" in isi)
    cek("memuat total cek hijau", "total cek hijau:" in isi)
    cek("menyatakan sumber (make hitung-verifier)", "make hitung-verifier" in isi)
    cek("memuat >= 20 verifier", len(verifier) >= 20, repr(len(verifier)))
    print()
    if FAIL:
        print("  [MERAH] verify_verifier_count: %d hijau, %d GAGAL" % (PASS, FAIL)); return 1
    print("  [ok]   verify_verifier_count: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
