#!/usr/bin/env python3
"""Pengunci: 'hijau' harus berarti make hijau (verifikasi SEMUA verifier + test), dan instruksi selaras."""
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


def baca(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def main():
    print("== verify_aturan_hijau ==")
    # REGENERASI: pengunci yang memeriksa artefak hasil-generate WAJIB meregenerasi dulu
    gen_sh = os.path.join(ROOT, "tools", "buat_resume_kit.sh")
    if os.path.exists(gen_sh):
        try:
            subprocess.run(["bash", gen_sh], capture_output=True, stdin=subprocess.DEVNULL, timeout=180)
        except Exception:
            pass
    runner = os.path.join(ROOT, "tools", "jalankan_semua_verifier.sh")
    cek("runner verifikasi ada", os.path.exists(runner))
    mk = baca(os.path.join(ROOT, "Makefile"))
    cek("Makefile punya target hijau", "\nhijau:" in mk or mk.startswith("hijau:"))
    cek("target hijau memanggil runner verifikasi", "jalankan_semua_verifier.sh" in mk)
    _bag = mk.split("hijau:")[1][:200] if "hijau:" in mk else ""
    cek("target hijau menjalankan make test", "make test" in _bag)
    cek("target verifikasi ada (dipakai runner)", "\nverifikasi:" in mk or mk.startswith("verifikasi:"))

    for nama in ("docs/V1.4.md", "docs/TARGET-BUKTI.md", "docs/DEPLOY-VPS.md"):
        isi = baca(os.path.join(ROOT, nama))
        cek("%s menyebut make hijau" % nama, "make hijau" in isi)
    cek("V1.4 memuat ATURAN HIJAU", "ATURAN HIJAU" in baca(os.path.join(ROOT, "docs", "V1.4.md")))
    cek("V1.4 menjelaskan gate tidak cukup", "TIDAK cukup" in baca(os.path.join(ROOT, "docs", "V1.4.md")))

    gen = baca(os.path.join(ROOT, "tools", "buat_resume_kit.sh"))
    cek("generator kit menyebut make hijau", "make hijau" in gen)
    dep = baca(os.path.join(ROOT, "tools", "deploy_vps.sh"))
    cek("deploy_vps memakai make hijau", "make hijau" in dep)

    if os.path.isdir(KIT):
        for nama in ("00-BACA-DULU.txt", "resume.sh", "TEMPEL-KE-CHAT-BARU.txt"):
            p = os.path.join(KIT, nama)
            if os.path.exists(p):
                cek("kit/%s menyebut make hijau" % nama, ("make hijau" in baca(p) or "make gate" in baca(p)))
        cek("SHA256SUMS kit ada", os.path.exists(os.path.join(KIT, "SHA256SUMS")))

    cek("angka kanonik docs/VERIFIER-COUNT.md ada", os.path.exists(os.path.join(ROOT, "docs", "VERIFIER-COUNT.md")))

    print()
    if FAIL:
        print("  [MERAH] verify_aturan_hijau: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_aturan_hijau: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
