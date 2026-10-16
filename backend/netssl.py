"""GALARDO - pemilih CA bundle + konteks TLS yang benar untuk macOS.

Masalah: Python dari Command Line Tools kadang tidak punya CA store yang valid,
sehingga HTTPS ke luar gagal dengan CERTIFICATE_VERIFY_FAILED. Itu mematikan
jalur bukti out-of-band (external_probe, observer) tanpa terlihat.

Modul ini memilih bundle yang benar-benar bisa dipakai, berurutan:
  1. SSL_CERT_FILE dari environment (kalau ada dan valid)
  2. certifi (kalau terpasang)
  3. bundle sistem macOS
"""

from __future__ import annotations

import os
import ssl

__all__ = ["CANDIDATES", "ca_file", "context", "verify_probe"]

CANDIDATES = (
    "/etc/ssl/cert.pem",
    "/etc/ssl/certs/ca-certificates.crt",
    "/usr/local/etc/openssl/cert.pem",
    "/opt/homebrew/etc/openssl@3/cert.pem",
)


def ca_file():
    """Kembalikan path CA bundle yang ada, atau None."""
    env = os.environ.get("SSL_CERT_FILE")
    if env and os.path.isfile(env):
        return env
    try:
        import certifi
        p = certifi.where()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    for c in CANDIDATES:
        if os.path.isfile(c):
            return c
    return None


def context(verify=True, cafile=None):
    """Konteks SSL. verify=False -> tidak memeriksa (untuk diagnosis)."""
    if not verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    f = cafile or ca_file()
    if f:
        try:
            return ssl.create_default_context(cafile=f)
        except Exception:
            pass
    return ssl.create_default_context()


def verify_probe(url="https://api.cloudflare.com/client/v4/", timeout=10):
    """Tes apakah HTTPS ke luar bisa diverifikasi. Kembalikan (ok, detail)."""
    import urllib.request
    try:
        urllib.request.urlopen(url, timeout=timeout, context=context())
        return True, "verifikasi TLS OK (ca=%s)" % (ca_file() or "default")
    except Exception as exc:
        return False, "%s" % str(exc)[:180]
