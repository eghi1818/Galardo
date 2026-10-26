#!/usr/bin/env python3
"""Verifier kesiapan deploy VPS (offline): skrip, target make, dokumen prosedur."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
    print("== verify_deploy_vps (offline) ==")
    sh = os.path.join(ROOT, "tools", "deploy_vps.sh")
    cek("tools/deploy_vps.sh ada", os.path.exists(sh))
    if not os.path.exists(sh):
        return 1
    isi = open(sh, encoding="utf-8").read()
    cek("skrip lolos bash -n", subprocess.run(["bash", "-n", sh], capture_output=True).returncode == 0)
    for tanda, label in (("make gate", "menjalankan make gate"), ("make test", "menjalankan make test"),
                         ("GALARDO_GATEWAY_URL", "memeriksa env anyip"), ("make tunnel", "menyebut make tunnel"),
                         ("TARGET-BUKTI.md", "menunjuk prosedur bukti")):
        cek("skrip: %s" % label, tanda in isi)

    mk = open(os.path.join(ROOT, "Makefile"), encoding="utf-8").read()
    cek("Makefile punya target deploy-vps", "\ndeploy-vps:" in mk or mk.startswith("deploy-vps:"))
    cek("target deploy-vps memanggil skrip", "tools/deploy_vps.sh" in mk)

    dok = open(os.path.join(ROOT, "docs", "DEPLOY-VPS.md"), encoding="utf-8").read()
    for tanda in ("rsync", "deploy_vps.sh", "verify_egress_rotation.py", "TARGET-BUKTI.md"):
        cek("dokumen prosedur memuat %s" % tanda, tanda in dok)

    print()
    if FAIL:
        print("  [MERAH] verify_deploy_vps: %d hijau, %d GAGAL" % (PASS, FAIL)); return 1
    print("  [ok]   verify_deploy_vps: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
