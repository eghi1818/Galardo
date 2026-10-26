#!/usr/bin/env python3
"""Angka cek NYATA tiap verifier -> docs/VERIFIER-COUNT.md.

Mode: (default) jalankan semua | --daftar (nama saja, cepat) | --dari-out (dari .out, tanpa jalan ulang)
"""
import glob
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "VERIFIER-COUNT.md")
RINGKAS = os.path.join(ROOT, ".out", "verifikasi-ringkas.txt")
RE_CEK = re.compile(r"(\d+)\s+cek hijau")
RE_GAGAL = re.compile(r"(\d+)\s+(?:GAGAL|gagal)")


def nama_verifier():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "tools", "verify_*.py")))


def tulis(baris, merah, catatan):
    total = sum(b[1] for b in baris)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# VERIFIER-COUNT - angka cek NYATA\n\n")
        fh.write("Dihasilkan oleh `make hitung-verifier` (tools/hitung_verifier.py).\n")
        fh.write("Kutip angka dari file ini, JANGAN dari ingatan. %s\n\n" % catatan)
        fh.write("| verifier | cek hijau | gagal | rc | detik |\n|---|---|---|---|---|\n")
        for nama, n, g, rc, dt in baris:
            fh.write("| %s | %d | %d | %d | %.1f |\n" % (nama, n, g, rc, dt))
        fh.write("\njumlah verifier: %d\n" % len(baris))
        fh.write("total cek hijau: %d\n" % total)
        fh.write("verifier merah: %s\n" % (", ".join(merah) if merah else "tidak ada"))
    print("verifier: %d | total cek hijau: %d | merah: %s" % (len(baris), total, merah or "tidak ada"))


def main():
    mode = "jalankan"
    if "--daftar" in sys.argv:
        mode = "daftar"
    elif "--dari-out" in sys.argv:
        mode = "dari_out"
    verifier = nama_verifier()

    if mode == "daftar":
        tulis([(v, 0, 0, 0, 0.0) for v in verifier], [], "(daftar nama; angka menyusul)")
        return 0

    if mode == "dari_out":
        rc_peta = {}
        if os.path.exists(RINGKAS):
            for ln in open(RINGKAS, encoding="utf-8"):
                b = ln.split(None, 1)
                if len(b) == 2:
                    rc_peta[b[1].strip()] = int(b[0])
        baris, merah = [], []
        for v in verifier:
            p = os.path.join(ROOT, ".out", "verifikasi-%s.txt" % v)
            keluaran = open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""
            cek = RE_CEK.findall(keluaran)
            gagal = RE_GAGAL.findall(keluaran)
            rc = rc_peta.get(v, 0)
            if rc != 0:
                merah.append(v)
            baris.append((v, int(cek[-1]) if cek else 0, int(gagal[-1]) if gagal else 0, rc, 0.0))
        tulis(baris, merah, "(angka dari .out/verifikasi-*.txt)")
        return 0

    baris, merah = [], []
    for v in verifier:
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", v)],
                               capture_output=True, text=True, timeout=300)
            keluaran, rc = (r.stdout or "") + (r.stderr or ""), r.returncode
        except subprocess.TimeoutExpired:
            keluaran, rc = "", 124
        cek = RE_CEK.findall(keluaran)
        gagal = RE_GAGAL.findall(keluaran)
        if rc != 0:
            merah.append(v)
        baris.append((v, int(cek[-1]) if cek else 0, int(gagal[-1]) if gagal else 0, rc, round(time.time() - t0, 1)))
    tulis(baris, merah, "(dijalankan sungguhan)")
    return 0 if not merah else 1


if __name__ == "__main__":
    sys.exit(main())
