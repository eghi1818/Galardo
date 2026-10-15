#!/usr/bin/env python3
"""
verify_crypto.py — uji known-answer dan adversarial untuk lapisan kepercayaan Tier 1.

Empat kelompok:
  A. Vektor known-answer RFC 8032 bagian 7.1 (public key, signature, verify)
     plus penolakan tamper, S >= L, dan public key salah.
  B. Semantik envelope: bentuk kanonik, roundtrip, tamper payload, replay nonce,
     kedaluwarsa dua arah, key id tak dikenal, kunci salah, input rusak.
  C. Keyring: buat, simpan, muat ulang antar proses, mode file 600.
  D. Kinerja tanda tangan/verifikasi di pure python.

Exit 0 hanya kalau semua check lolos.
"""

import base64
import copy
import json
import os
import shutil
import sys
import tempfile
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend import ed25519, envelope  # noqa: E402

PASSED = []
FAILED = []


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print("  PASS  " + name)
    else:
        FAILED.append(name)
        print("  FAIL  " + name + ("  <-- " + str(detail) if detail != "" else ""))


# RFC 8032 bagian 7.1: (nama, secret, public, message, signature) dalam hex
RFC_VECTORS = [
    ("TEST 1 (pesan kosong)",
     "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
     "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("TEST 2 (1 byte)",
     "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
     "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("TEST 3 (2 byte)",
     "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
     "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


def test_rfc_vectors():
    for name, sk_hex, pk_hex, msg_hex, sig_hex in RFC_VECTORS:
        sk = bytes.fromhex(sk_hex)
        pk = bytes.fromhex(pk_hex)
        msg = bytes.fromhex(msg_hex)
        want = bytes.fromhex(sig_hex)

        got_pk = ed25519.publickey(sk)
        check("A publickey " + name, got_pk == pk, got_pk.hex())

        got_sig = ed25519.sign(msg, sk)
        check("A signature " + name, got_sig == want, got_sig.hex())

        check("A verify " + name, ed25519.verify(want, msg, pk) is True)

        bad_msg = (bytes([msg[0] ^ 0x01]) + msg[1:]) if msg else b"\x00"
        check("A verify tolak pesan diubah " + name, ed25519.verify(want, bad_msg, pk) is False)

        s_int = int.from_bytes(want[32:], "little")
        forged = want[:32] + (s_int + ed25519.L).to_bytes(32, "little")
        check("A verify tolak S >= L " + name, ed25519.verify(forged, msg, pk) is False)

        bad_pk = bytes([pk[0] ^ 0x01]) + pk[1:]
        check("A verify tolak public key salah " + name, ed25519.verify(want, msg, bad_pk) is False)

        bad_sig = want[:63] + bytes([want[63] ^ 0x01])
        check("A verify tolak tanda tangan diubah " + name, ed25519.verify(bad_sig, msg, pk) is False)

    check("A verify tolak panjang tanda tangan salah", ed25519.verify(b"\x00" * 63, b"x", b"\x01" * 32) is False)
    check("A verify tolak panjang pk salah", ed25519.verify(b"\x00" * 64, b"x", b"\x01" * 31) is False)


def test_canonical():
    check("B canonical urut + tanpa spasi",
          envelope.canonical({"b": 1, "a": 2}) == b'{"a":2,"b":1}')
    check("B canonical deterministik",
          envelope.canonical({"x": [1, 2], "y": {"z": 3}}) == envelope.canonical({"y": {"z": 3}, "x": [1, 2]}))
    check("B canonical beda untuk payload beda",
          envelope.canonical({"a": 1}) != envelope.canonical({"a": 2}))


def test_envelope():
    sk, pk = envelope.keypair()
    kid = envelope.key_id(pk)
    trust = {kid: pk}
    now = time.time()

    env = envelope.sign_envelope({"action": "shard", "n": 3}, sk, ts=now)
    ok, reason, payload = envelope.verify_envelope(env, trust, now=now, replay=set())
    check("B roundtrip envelope sah", ok and payload == {"action": "shard", "n": 3}, reason)
    check("B kid envelope = hash pk", env["body"]["kid"] == kid)

    tampered = copy.deepcopy(env)
    tampered["body"]["payload"]["n"] = 4
    ok, reason, _ = envelope.verify_envelope(tampered, trust, now=now)
    check("B tolak payload diubah", (not ok) and reason == "bad_signature", reason)

    tampered2 = copy.deepcopy(env)
    tampered2["body"]["nonce"] = "deadbeefdeadbeef"
    ok, reason, _ = envelope.verify_envelope(tampered2, trust, now=now)
    check("B tolak nonce diubah", (not ok) and reason == "bad_signature", reason)

    tampered3 = copy.deepcopy(env)
    tampered3["body"]["kid"] = "0000000000000000"
    ok, reason, _ = envelope.verify_envelope(tampered3, trust, now=now)
    check("B tolak kid diubah (jadi tak dikenal)", (not ok) and reason == "unknown_kid", reason)

    seen = set()
    ok, reason, _ = envelope.verify_envelope(env, trust, now=now, replay=seen)
    check("B penerimaan pertama lolos", ok, reason)
    ok, reason, _ = envelope.verify_envelope(env, trust, now=now, replay=seen)
    check("B replay nonce ditolak", (not ok) and reason == "replay", reason)

    fresh = envelope.sign_envelope({"a": 1}, sk)
    ok, reason, _ = envelope.verify_envelope(fresh, trust, now=now - 1000)
    check("B tolak envelope terlalu tua", (not ok) and reason == "stale", reason)
    ok, reason, _ = envelope.verify_envelope(fresh, trust, now=now + 1000)
    check("B tolak envelope dari masa depan", (not ok) and reason == "stale", reason)

    ok, reason, _ = envelope.verify_envelope(env, {}, now=now)
    check("B tolak key id tak dikenal", (not ok) and reason == "unknown_kid", reason)

    sk2, pk2 = envelope.keypair()
    ok, reason, _ = envelope.verify_envelope(env, {kid: pk2}, now=now)
    check("B tolak kunci yang salah", (not ok) and reason == "bad_signature", reason)

    ok, reason, _ = envelope.verify_envelope([], trust, now=now)
    check("B tolak non-object", (not ok) and reason == "not_an_object", reason)
    ok, reason, _ = envelope.verify_envelope({}, trust, now=now)
    check("B tolak envelope rusak", (not ok) and reason == "malformed", reason)
    ok, reason, _ = envelope.verify_envelope({"body": env["body"], "sig": "!!!"}, trust, now=now)
    check("B tolak sig bukan base64", (not ok) and reason == "bad_sig_encoding", reason)

    badver = copy.deepcopy(env)
    badver["body"]["v"] = 99
    ok, reason, _ = envelope.verify_envelope(badver, trust, now=now)
    check("B tolak versi asing", (not ok) and reason == "bad_version", reason)

    nononce = copy.deepcopy(env)
    nononce["body"]["nonce"] = "x"
    ok, reason, _ = envelope.verify_envelope(nononce, trust, now=now)
    check("B tolak nonce terlalu pendek", (not ok) and reason == "bad_nonce", reason)

    check("B tanpa cache replay envelope tetap sah",
          envelope.verify_envelope(env, trust, now=now)[0] is True)


def test_keyring():
    d = tempfile.mkdtemp(prefix="galardo-crypto-")
    try:
        path = os.path.join(d, "keys.json")
        kr = envelope.Keyring(path)
        kid = kr.create("controller")
        check("C keyring mengembalikan kid 16 hex", len(kid) == 16, kid)
        check("C file keyring ditulis", os.path.exists(path))
        mode = oct(os.stat(path).st_mode & 0o777)
        check("C mode file keyring 600", mode == "0o600", mode)

        kr2 = envelope.Keyring(path)
        check("C muat ulang melihat kunci", kid in kr2.keys)
        check("C secret identik setelah muat ulang", kr2.secret(kid) == kr.secret(kid))
        check("C public_map tanpa secret",
              set(kr2.public_map()[kid]) == set(bytes.fromhex(kr2.keys[kid]["public"])))

        env = envelope.sign_envelope({"x": 1}, kr2.secret(kid))
        ok, reason, _ = envelope.verify_envelope(env, kr2.public_map(), replay=set())
        check("C tanda tangan lintas muat ulang terverifikasi", ok, reason)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_timing():
    sk, pk = envelope.keypair()
    n = 10
    t0 = time.time()
    for _ in range(n):
        ed25519.sign(b"x" * 64, sk)
    sign_ms = (time.time() - t0) * 1000.0 / n
    sig = ed25519.sign(b"x" * 64, sk)
    t0 = time.time()
    for _ in range(n):
        ed25519.verify(sig, b"x" * 64, pk)
    ver_ms = (time.time() - t0) * 1000.0 / n
    print("  INFO  sign %.1f ms/op, verify %.1f ms/op (pure python)" % (sign_ms, ver_ms))
    check("D sign di bawah 200 ms", sign_ms < 200.0, "%.1f" % sign_ms)
    check("D verify di bawah 200 ms", ver_ms < 200.0, "%.1f" % ver_ms)


def main():
    print("=" * 62)
    print("  VERIFIKASI TIER 1 — ED25519 (RFC 8032) + ENVELOPE")
    print("=" * 62)
    print()
    print("--- A. Vektor known-answer RFC 8032 ---")
    test_rfc_vectors()
    print()
    print("--- B. Semantik envelope + kanonik ---")
    test_canonical()
    test_envelope()
    print()
    print("--- C. Persistensi keyring ---")
    test_keyring()
    print()
    print("--- D. Kinerja ---")
    test_timing()
    print()
    print("=" * 62)
    print("RESULTS: %d passed, %d failed" % (len(PASSED), len(FAILED)))
    if FAILED:
        print("GAGAL:")
        for f in FAILED:
            print("  - " + f)
    print("=" * 62)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
