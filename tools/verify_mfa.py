#!/usr/bin/env python3
"""Tes offline mfa.py memakai vektor resmi RFC 6238 (SHA1, 8 digit)."""
import os, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import mfa

PASS = FAIL = 0
SEC = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"   # ASCII "12345678901234567890"


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


print("== A. vektor RFC 6238 (8 digit) ==")
VEC = [(59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"),
       (1234567890, "89005924"), (2000000000, "69279037"), (20000000000, "65353130")]
for t, exp in VEC:
    got = mfa.totp(SEC, t, digits=8)
    check("A t=%d -> %s" % (t, exp), got == exp, got)

print("== B. 6 digit = 6 digit terakhir ==")
check("B 6 digit cocok dengan ekor vektor", mfa.totp(SEC, 59) == "287082", mfa.totp(SEC, 59))
check("B panjang 6", len(mfa.totp(SEC, 59)) == 6)
check("B leading zero dipertahankan", mfa.totp(SEC, 1111111109) == "081804", mfa.totp(SEC, 1111111109))

print("== C. verify ==")
code = mfa.totp(SEC, 59)
ok, step, drift = mfa.verify(SEC, code, t=59)
check("C kode benar diterima", ok is True and step == 1 and drift == 0, (ok, step, drift))
ok2, _, _ = mfa.verify(SEC, "000000", t=59)
check("C kode salah ditolak", ok2 is False)
ok3, _, _ = mfa.verify(SEC, "", t=59)
check("C kode kosong ditolak", ok3 is False)
ok4, _, _ = mfa.verify("", code, t=59)
check("C secret kosong ditolak", ok4 is False)
ok5, _, _ = mfa.verify(SEC, "abc123", t=59)
check("C kode non-digit ditolak", ok5 is False)

print("== D. jendela drift ==")
prev = mfa.totp(SEC, 59 - 30)
ok6, _, d6 = mfa.verify(SEC, prev, t=59, window=1)
check("D step sebelumnya diterima (window 1)", ok6 is True and d6 == -1, (ok6, d6))
ok7, _, _ = mfa.verify(SEC, prev, t=59, window=0)
check("D step sebelumnya ditolak (window 0)", ok7 is False)
far = mfa.totp(SEC, 59 - 120)
ok8, _, _ = mfa.verify(SEC, far, t=59, window=1)
check("D step jauh ditolak", ok8 is False)

print("== E. replay ==")
ok9, step9, _ = mfa.verify(SEC, code, t=59, last_step=step)
check("E replay step sama ditolak", ok9 is False and step9 == step, (ok9, step9))
ok10, _, _ = mfa.verify(SEC, mfa.totp(SEC, 89), t=89, last_step=1)
check("E step baru diterima", ok10 is True)

print("== F. secret & uri ==")
s = mfa.gen_secret()
check("F secret base32 32 char", len(s) == 32 and s.isupper(), s)
check("F dua secret berbeda", mfa.gen_secret() != mfa.gen_secret())
u = mfa.provisioning_uri(SEC, "op@contoh.test")
check("F uri otpauth", u.startswith("otpauth://totp/") and "secret=" in u, u)
check("F uri memuat issuer", "issuer=Galardo" in u, u)

print("== G. waktu negatif (sebelum epoch) ==")
check("G t=-61 tidak meledak", isinstance(mfa.totp(SEC, -61), str), mfa.totp(SEC, -61))
check("G t=-61 panjang 6", len(mfa.totp(SEC, -61)) == 6)
check("G t=0 jalan", mfa.totp(SEC, 0) == mfa.totp(SEC, 0))

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
