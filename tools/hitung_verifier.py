#!/usr/bin/env python3
"""Hitung angka cek tiap verifier secara NYATA (bukan dari ingatan) -> docs/VERIFIER-COUNT.md.

Dipakai oleh `make hitung-verifier`. Menjalankan tiap tools/verify_*.py, mengambil baris
terakhir 'N cek hijau' dan rc-nya. Angka inilah yang boleh dikutip di HASIL/STATUS.
"""
import glob
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "VERIFIER-COUNT.md")
RE_CEK = re.compile(r"(\d+)\s+cek hijau")
RE_GAGAL = re.compile(r"(\d+)\s+(?:GAGAL|gagal)")


def main():
    verifier = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "tools", "verify_*.py")))
    baris = []
    total_cek = 0
    merah = []
    for nama in verifier:
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", nama)],
                               capture_output=True, text=True, timeout=300)
            keluaran = (r.stdout or "") + (r.stderr or "")
            rc = r.returncode
        except subprocess.TimeoutExpired:
            keluaran, rc = "", 124
        cek = RE_CEK.findall(keluaran)
        gagal = RE_GAGAL.findall(keluaran)
        n = int(cek[-1]) if cek else 0
        g = int(gagal[-1]) if gagal else 0
        total_cek += n
        if rc != 0:
            merah.append(nama)
        baris.append((nama, n, g, rc, round(time.time() - t0, 1)))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# VERIFIER-COUNT - angka cek NYATA\n\n")
        fh.write("Dihasilkan oleh `make hitung-verifier` (tools/hitung_verifier.py).\n")
        fh.write("Kutip angka dari file ini, JANGAN dari ingatan.\n\n")
        fh.write("| verifier | cek hijau | gagal | rc | detik |\n|---|---|---|---|---|\n")
        for nama, n, g, rc, dt in baris:
            fh.write("| %s | %d | %d | %d | %.1f |\n" % (nama, n, g, rc, dt))
        fh.write("\njumlah verifier: %d\n" % len(verifier))
        fh.write("total cek hijau: %d\n" % total_cek)
        fh.write("verifier merah: %s\n" % (", ".join(merah) if merah else "tidak ada"))

    # KONFIRMASI ULANG: verifier merah dijalankan sekali lagi (bisa jadi merah hanya karena berkas
    # daftar masih basi). Kalau lulus di percobaan kedua, baris diperbarui dan dikeluarkan dari merah.
    if merah:
        for i, (nama, n, g, rc, dt) in enumerate(baris):
            if rc == 0:
                continue
            try:
                r2 = subprocess.run([sys.executable, os.path.join(ROOT, "tools", nama)],
                                    capture_output=True, text=True, timeout=300)
                if r2.returncode == 0:
                    kel2 = (r2.stdout or "") + (r2.stderr or "")
                    c2 = RE_CEK.findall(kel2)
                    baris[i] = (nama, int(c2[-1]) if c2 else 0, 0, 0, dt)
                    total_cek += (int(c2[-1]) if c2 else 0) - n
                    merah.remove(nama)
            except Exception:
                pass
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("# VERIFIER-COUNT - angka cek NYATA\n\n")
            fh.write("Dihasilkan oleh `make hitung-verifier` (tools/hitung_verifier.py).\n")
            fh.write("Kutip angka dari file ini, JANGAN dari ingatan.\n\n")
            fh.write("| verifier | cek hijau | gagal | rc | detik |\n|---|---|---|---|---|\n")
            for nama, n, g, rc, dt in baris:
                fh.write("| %s | %d | %d | %d | %.1f |\n" % (nama, n, g, rc, dt))
            fh.write("\njumlah verifier: %d\n" % len(verifier))
            fh.write("total cek hijau: %d\n" % total_cek)
            fh.write("verifier merah: %s\n" % (", ".join(merah) if merah else "tidak ada"))

    print("verifier: %d | total cek hijau: %d | merah: %s" % (len(verifier), total_cek, merah or "tidak ada"))
    print("ditulis: docs/VERIFIER-COUNT.md")
    return 0 if not merah else 1


if __name__ == "__main__":
    sys.exit(main())
