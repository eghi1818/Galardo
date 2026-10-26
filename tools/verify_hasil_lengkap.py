#!/usr/bin/env python3
"""Pengunci kelengkapan jejak: setiap STEP di docs/STEPLOG.md wajib punya docs/HASIL-<n>.md.

Latar: STEP-182 pernah tercatat di STEPLOG tanpa file HASIL (draft digabung ke HASIL-181).
Verifier ini mencegah kelas kelalaian yang sama.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEPLOG = os.path.join(ROOT, "docs", "STEPLOG.md")
MIN_STEP = 174

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
    print("== verify_hasil_lengkap ==")
    if not os.path.exists(STEPLOG):
        cek("docs/STEPLOG.md ada", False)
        return 1
    isi = open(STEPLOG, encoding="utf-8").read()
    nomor = sorted({int(n) for n in re.findall(r"(?m)^-\s*STEP-(\d+)", isi)})
    cek("STEPLOG memuat baris STEP", len(nomor) > 0, repr(len(nomor)))

    bolong = [n for n in nomor if n >= MIN_STEP and not os.path.exists(os.path.join(ROOT, "docs", "HASIL-%d.md" % n))]
    cek("tiap STEP >= %d punya docs/HASIL-<n>.md" % MIN_STEP, not bolong, "bolong: %s" % bolong)

    tipis = []
    tanpa_isi = []
    for n in nomor:
        if n < MIN_STEP:
            continue
        p = os.path.join(ROOT, "docs", "HASIL-%d.md" % n)
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read()
        if len(t) < 150:
            tipis.append(n)
        if not any(k in t for k in ("angka", "AKAR", "ISI", "TUJUAN")):
            tanpa_isi.append(n)
    cek("tidak ada HASIL yang terlalu tipis", not tipis, repr(tipis))
    cek("tiap HASIL memuat angka/AKAR/ISI/TUJUAN", not tanpa_isi, repr(tanpa_isi))

    # HASIL yang mengklaim hijau harus menyebut angka rc
    tanpa_angka = []
    for n in nomor:
        if n < MIN_STEP:
            continue
        p = os.path.join(ROOT, "docs", "HASIL-%d.md" % n)
        if os.path.exists(p) and "rc=" not in open(p, encoding="utf-8").read():
            tanpa_angka.append(n)
    cek("tiap HASIL menuliskan angka rc", not tanpa_angka, repr(tanpa_angka))

    print()
    if FAIL:
        print("  [MERAH] verify_hasil_lengkap: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_hasil_lengkap: %d cek hijau (%d STEP diperiksa)" % (PASS, len(nomor)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
