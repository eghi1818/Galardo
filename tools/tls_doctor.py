#!/usr/bin/env python3
"""Diagnosa TLS: bisa atau tidak HTTPS ke luar diverifikasi.

PENTING: urllib melempar HTTPError untuk 4xx/5xx. Itu BUKAN kegagalan TLS.
Kesalahan menilai ini bikin diagnosis salah arah.
"""
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

import netssl  # noqa: E402

TARGET = os.environ.get("GALARDO_TLS_TARGET", "https://api.cloudflare.com/client/v4/")


def probe(ctx):
    try:
        urllib.request.urlopen(TARGET, timeout=10, context=ctx)
        return True, "OK (2xx)"
    except urllib.error.HTTPError as e:
        return True, "OK - TLS lolos, server jawab HTTP %d" % e.code
    except Exception as e:
        return False, str(e)[:170]


print("== 1. jalur CA bawaan python ==")
p = ssl.get_default_verify_paths()
print("  cafile default : %s" % p.cafile)
print("  ada            : %s" % os.path.isfile(p.cafile or ""))
print("  certifi        : %s" % (netssl.ca_file() or "-"))
print()

print("== 2. uji koneksi ==")
tests = [
    ("default context", ssl.create_default_context()),
    ("netssl (ca=%s)" % (netssl.ca_file() or "-"), netssl.context()),
    ("tanpa verifikasi", netssl.context(verify=False)),
]
verdict = {}
for label, ctx in tests:
    ok, detail = probe(ctx)
    verdict[label] = ok
    print("  [%s] %-52s %s" % ("v" if ok else "X", label, detail))
print()

print("== 3. issuer (deteksi TLS interception) ==")
try:
    out = subprocess.run(
        "openssl s_client -connect api.cloudflare.com:443 "
        "-servername api.cloudflare.com </dev/null 2>/dev/null "
        "| openssl x509 -noout -issuer",
        shell=True, capture_output=True, text=True, timeout=20).stdout.strip()
    print("  %s" % (out or "(openssl tidak tersedia)"))
except Exception as e:
    print("  gagal: %s" % e)
print()

print("== KESIMPULAN ==")
if verdict.get("netssl (ca=%s)" % (netssl.ca_file() or "-")):
    print("  TLS BISA diverifikasi lewat netssl. Pakai netssl.context() di semua modul HTTPS.")
    print("  ca_file = %s" % netssl.ca_file())
    sys.exit(0)
if verdict.get("tanpa verifikasi"):
    print("  Hanya mode tanpa verifikasi yang jalan -> kemungkinan interception.")
    sys.exit(0)
print("  TLS benar-benar tidak bisa dipakai.")
sys.exit(1)
