"""
ed25519.py — tanda tangan Ed25519 (RFC 8032) murni Python 3.9 stdlib.

Tanpa pip, tanpa paket cryptography, tanpa ctypes. Hanya hashlib.

Rujukan: RFC 8032 bagian 5.1. Titik direpresentasikan sebagai koordinat
twisted Edwards diperluas (X:Y:Z:T) supaya penambahan titik tidak butuh
inversi modular; inversi hanya sekali saat encoding.

Diverifikasi terhadap vektor known-answer RFC 8032 bagian 7.1 di
tools/verify_crypto.py.

API:
    derive_seed() -> bytes32
    publickey(sk: bytes32) -> bytes32
    sign(msg: bytes, sk: bytes32) -> bytes64
    verify(sig: bytes64, msg: bytes, pk: bytes32) -> bool
"""

import hashlib
import secrets

__all__ = ["P", "L", "derive_seed", "publickey", "sign", "verify"]

# --- konstanta kurva -------------------------------------------------------
P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, P - 2, P)) % P
SQRT_M1 = pow(2, (P - 1) // 4, P)

IDENTITY = (0, 1, 1, 0)


def _recover_x(y):
    xx = (y * y - 1) * pow(D * y * y + 1, P - 2, P) % P
    x = pow(xx, (P + 3) // 8, P)
    if (x * x - xx) % P != 0:
        x = (x * SQRT_M1) % P
    if x % 2 != 0:
        x = P - x
    return x


_BY = (4 * pow(5, P - 2, P)) % P
_BX = _recover_x(_BY)
BASE = (_BX, _BY, 1, (_BX * _BY) % P)


def _add(p1, p2):
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = ((y1 - x1) * (y2 - x2)) % P
    b = ((y1 + x1) * (y2 + x2)) % P
    c = (2 * t1 * t2 * D) % P
    dd = (2 * z1 * z2) % P
    e = b - a
    f = dd - c
    g = dd + c
    h = b + a
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _double(p):
    x1, y1, z1, _t1 = p
    a = x1 * x1 % P
    b = y1 * y1 % P
    c = 2 * z1 * z1 % P
    d = (-a) % P
    e = ((x1 + y1) * (x1 + y1) - a - b) % P
    g = (d + b) % P
    f = (g - c) % P
    h = (d - b) % P
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _scalar_mul(point, scalar):
    result = IDENTITY
    addend = point
    while scalar > 0:
        if scalar & 1:
            result = _add(result, addend)
        addend = _double(addend)
        scalar >>= 1
    return result


def _encode(point):
    x, y, z, _t = point
    zi = pow(z, P - 2, P)
    x = x * zi % P
    y = y * zi % P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decode(encoded):
    if len(encoded) != 32:
        raise ValueError("titik harus 32 byte")
    n = int.from_bytes(encoded, "little")
    y = n & ((1 << 255) - 1)
    sign = n >> 255
    x = _recover_x(y)
    if (x & 1) != sign:
        x = P - x
    if (-x * x + y * y - 1 - D * x * x * y * y) % P != 0:
        raise ValueError("titik tidak ada di kurva")
    return (x, y, 1, x * y % P)


def _clamped_secret(sk):
    if len(sk) != 32:
        raise ValueError("secret key harus 32 byte")
    h = hashlib.sha512(sk).digest()
    a = bytearray(h[:32])
    a[0] &= 248
    a[31] &= 127
    a[31] |= 64
    return int.from_bytes(bytes(a), "little"), h[32:]


def derive_seed():
    return secrets.token_bytes(32)


def publickey(sk):
    a, _prefix = _clamped_secret(sk)
    return _encode(_scalar_mul(BASE, a))


def sign(msg, sk):
    if not isinstance(msg, (bytes, bytearray)):
        raise TypeError("msg harus bytes")
    msg = bytes(msg)
    a, prefix = _clamped_secret(sk)
    pub = _encode(_scalar_mul(BASE, a))
    r = int.from_bytes(hashlib.sha512(prefix + msg).digest(), "little") % L
    r_enc = _encode(_scalar_mul(BASE, r))
    k = int.from_bytes(hashlib.sha512(r_enc + pub + msg).digest(), "little") % L
    s = (r + k * a) % L
    return r_enc + s.to_bytes(32, "little")


def verify(sig, msg, pk):
    if not isinstance(sig, (bytes, bytearray)) or len(sig) != 64:
        return False
    if not isinstance(pk, (bytes, bytearray)) or len(pk) != 32:
        return False
    if not isinstance(msg, (bytes, bytearray)):
        return False
    msg = bytes(msg)
    s = int.from_bytes(sig[32:], "little")
    if s >= L:
        return False
    try:
        a_point = _decode(pk)
        r_point = _decode(sig[:32])
    except ValueError:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + bytes(pk) + msg).digest(), "little") % L
    return _encode(_scalar_mul(BASE, s)) == _encode(_add(r_point, _scalar_mul(a_point, k)))
