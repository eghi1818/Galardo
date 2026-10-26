#!/usr/bin/env python3
"""Verifier kit resume (minimal): root hanya berisi yang perlu, arsip untuk sisanya."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.environ.get("GALARDO_KIT") or os.path.join(os.path.expanduser("~"), "Desktop", "GALARDO-RESUME")
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
    print("== verify_resume_kit (offline) ==")
    gen = os.path.join(ROOT, "tools", "buat_resume_kit.sh")
    cek("generator ada", os.path.exists(gen))
    if not os.path.exists(gen):
        return 1
    r = subprocess.run(["bash", "-n", gen], capture_output=True, stdin=subprocess.DEVNULL, text=True)
    cek("generator lolos bash -n", r.returncode == 0, r.stderr[:120])
    r = subprocess.run(["bash", gen], capture_output=True, stdin=subprocess.DEVNULL, text=True, timeout=120)
    cek("generator berjalan tanpa error", r.returncode == 0, r.stderr[-200:])

    lampiran = ["01-GOAL-GALARDO.md", "02-STATUS-SEKARANG.md", "03-V1.4.md", "04-TARGET-BUKTI.md"]
    for nama in lampiran:
        cek("lampiran %s ada" % nama, os.path.exists(os.path.join(KIT, nama)))
    cek("TEMPEL-KE-CHAT-BARU.txt ada", os.path.exists(os.path.join(KIT, "TEMPEL-KE-CHAT-BARU.txt")))
    cek("00-BACA-DULU.txt ada", os.path.exists(os.path.join(KIT, "00-BACA-DULU.txt")))
    cek("resume.sh ada + bisa dieksekusi",
        os.path.exists(os.path.join(KIT, "resume.sh")) and os.access(os.path.join(KIT, "resume.sh"), os.X_OK))
    cek("SHA256SUMS ada", os.path.exists(os.path.join(KIT, "SHA256SUMS")))

    arsip = os.path.join(KIT, "arsip")
    cek("arsip/ ada", os.path.isdir(arsip))
    if os.path.isdir(arsip):
        cek("arsip/ berisi >= 8 berkas", len(os.listdir(arsip)) >= 8, repr(len(os.listdir(arsip))))

    # root TIDAK boleh punya folder docs (penyebab kebingungan)
    cek("root kit tidak punya folder docs/", not os.path.isdir(os.path.join(KIT, "docs")))

    root_files = sorted(f for f in os.listdir(KIT) if os.path.isfile(os.path.join(KIT, f)))
    cek("root kit <= 8 berkas (minimal)", len(root_files) <= 8, repr(root_files))

    r = subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=KIT, capture_output=True, stdin=subprocess.DEVNULL, text=True)
    cek("SHA256SUMS terverifikasi", r.returncode == 0, (r.stdout + r.stderr)[-160:])

    sh = os.path.join(KIT, "resume.sh")
    r = subprocess.run(["bash", "-n", sh], capture_output=True, stdin=subprocess.DEVNULL, text=True)
    cek("resume.sh lolos bash -n", r.returncode == 0, r.stderr[:120])

    baca = open(os.path.join(KIT, "00-BACA-DULU.txt"), encoding="utf-8").read() if os.path.exists(os.path.join(KIT, "00-BACA-DULU.txt")) else ""
    cek("00-BACA menyebut 4 lampiran + make hijau",
        "01-GOAL-GALARDO.md" in baca and ("make hijau" in baca or "make gate" in baca))
    cek("00-BACA menyebut make hijau", "make hijau" in baca)

    print()
    if FAIL:
        print("  [MERAH] verify_resume_kit: %d hijau, %d GAGAL" % (PASS, FAIL)); return 1
    print("  [ok]   verify_resume_kit: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
