#!/usr/bin/env python3
"""Verifier tunnel pihak ketiga (offline). Kehadiran cloudflared tidak memerahkan gate."""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def main():
    print("== verify_tunnel_wired (offline) ==")
    sh = os.path.join(ROOT, "tools", "tunnel.sh")
    mk = os.path.join(ROOT, "Makefile")
    cek("tools/tunnel.sh ada", os.path.exists(sh))
    if os.path.exists(sh):
        with open(sh, encoding="utf-8") as fh:
            isi = fh.read()
        cek("tunnel.sh punya mode token", "GALARDO_CF_TUNNEL_TOKEN" in isi and "--token" in isi)
        cek("tunnel.sh punya mode cepat", "--url" in isi and "trycloudflare" in isi)
        cek("tunnel.sh mengarah ke port lokal", "127.0.0.1" in isi)
        cek("tunnel.sh gagal rapi bila cloudflared absen", "cloudflared belum terpasang" in isi)
        r = subprocess.run(["bash", "-n", sh], capture_output=True, text=True)
        cek("tunnel.sh lolos bash -n", r.returncode == 0, r.stderr[:120])

    with open(mk, encoding="utf-8") as fh:
        m = fh.read()
    cek("Makefile punya target tunnel", "\ntunnel:" in m or m.startswith("tunnel:"))
    cek("target tunnel memanggil tunnel.sh", "tools/tunnel.sh" in m)

    if shutil.which("cloudflared"):
        r = subprocess.run(["cloudflared", "--version"], capture_output=True, text=True, timeout=20)
        cek("cloudflared terpasang & jalan", r.returncode == 0, r.stderr[:120])
    else:
        skip("cloudflared --version", "belum terpasang (brew install cloudflared)")

    print()
    if FAIL:
        print("  [MERAH] verify_tunnel_wired: %d hijau, %d GAGAL, %d skip" % (PASS, FAIL, SKIP))
        return 1
    print("  [ok]   verify_tunnel_wired: %d cek hijau, %d skip" % (PASS, SKIP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
