"""MFA TOTP (RFC 6238). Stdlib saja: hmac + base64 + struct."""
from __future__ import annotations

import base64, hashlib, hmac, os, struct, time, urllib.parse

DIGITS = 6
PERIOD = 30
ISSUER = "Galardo"


def gen_secret(nbytes=20):
    return base64.b32encode(os.urandom(nbytes)).decode().rstrip("=")


def _key(secret):
    s = (secret or "").upper().strip()
    s += "=" * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s)


def totp(secret, t=None, digits=DIGITS, period=PERIOD):
    t = int(time.time() if t is None else t)
    msg = struct.pack(">Q", (t // period) & 0xFFFFFFFFFFFFFFFF)
    digest = hmac.new(_key(secret), msg, hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[off:off + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def verify(secret, code, t=None, window=1, last_step=None):
    """(ok, step, drift). Replay ditolak bila step <= last_step."""
    code = (code or "").strip()
    if not secret or len(code) < 6 or not code.isdigit():
        return False, None, None
    step = int(time.time() if t is None else t) // PERIOD
    for d in range(-window, window + 1):
        if totp(secret, (step + d) * PERIOD, digits=len(code)) == code:
            if last_step is not None and (step + d) <= int(last_step):
                return False, step + d, d
            return True, step + d, d
    return False, None, None


def provisioning_uri(secret, label, issuer=ISSUER):
    q = urllib.parse.urlencode({"secret": secret, "issuer": issuer,
                                "digits": DIGITS, "period": PERIOD})
    name = urllib.parse.quote("%s:%s" % (issuer, label))
    return "otpauth://totp/%s?%s" % (name, q)
