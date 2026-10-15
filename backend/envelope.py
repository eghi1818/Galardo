"""
envelope.py — envelope bertanda tangan + anti-replay untuk kepercayaan
controller <-> worker.

Murni stdlib, memakai backend.ed25519 (RFC 8032).

Format di kabel (JSON):
    {
      "body": {"v": 1, "kid": "<key id>", "ts": <unix detik>,
               "nonce": "<16 hex>", "payload": {...}},
      "sig":  "<base64 tanda tangan ed25519 atas canonical_json(body)>"
    }

Canonical JSON = json.dumps(..., sort_keys=True, separators=(",", ":"))
di-encode UTF-8, sehingga kedua sisi menandatangani byte yang identik.
Semua field body ikut ditandatangani, termasuk kid/ts/nonce.

Urutan verifikasi (berhenti di kegagalan pertama):
    1. struktur dan versi
    2. key id dikenal (kid tak dikenal ditolak, tidak pernah dipercaya)
    3. timestamp di dalam jendela kesegaran (dua arah)
    4. nonce belum pernah dilihat (cache replay)
    5. tanda tangan atas body kanonik

Tidak ada payload yang dieksekusi sebelum langkah 5 lolos.
"""

import base64
import hashlib
import json
import os
import secrets
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend import ed25519

VERSION = 1
DEFAULT_WINDOW = 300.0
STATE_DIR = ".galardo"
KEYFILE = "keys.json"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def key_id(public_key):
    return hashlib.sha256(public_key).hexdigest()[:16]


def keypair():
    sk = ed25519.derive_seed()
    return sk, ed25519.publickey(sk)


def sign_envelope(payload, secret_key, kid=None, ts=None, nonce=None):
    public_key = ed25519.publickey(secret_key)
    body = {
        "v": VERSION,
        "kid": kid or key_id(public_key),
        "ts": int(time.time() if ts is None else ts),
        "nonce": nonce or secrets.token_hex(8),
        "payload": payload,
    }
    sig = ed25519.sign(canonical(body), secret_key)
    return {"body": body, "sig": base64.b64encode(sig).decode("ascii")}


def verify_envelope(envelope, trust, window=DEFAULT_WINDOW, now=None, replay=None):
    """Kembalikan (ok, reason, payload).

    trust  : {kid: public_key_bytes}
    replay : set() nonce yang sudah dilihat; dimutasi kalau bukan None
    """
    now = time.time() if now is None else now
    if not isinstance(envelope, dict):
        return False, "not_an_object", None
    body = envelope.get("body")
    sig_b64 = envelope.get("sig")
    if not isinstance(body, dict) or not isinstance(sig_b64, str):
        return False, "malformed", None
    if body.get("v") != VERSION:
        return False, "bad_version", None
    kid = body.get("kid")
    if kid not in trust:
        return False, "unknown_kid", None
    ts = body.get("ts")
    if not isinstance(ts, int):
        return False, "bad_ts", None
    if abs(now - ts) > window:
        return False, "stale", None
    nonce = body.get("nonce")
    if not isinstance(nonce, str) or len(nonce) < 8:
        return False, "bad_nonce", None
    try:
        sig = base64.b64decode(sig_b64, validate=True)
    except Exception:
        return False, "bad_sig_encoding", None
    if not ed25519.verify(sig, canonical(body), trust[kid]):
        return False, "bad_signature", None
    if replay is not None:
        if nonce in replay:
            return False, "replay", None
        replay.add(nonce)
    return True, "ok", body.get("payload")


class Keyring:
    """Menyimpan pasangan kunci di .galardo/keys.json (chmod 600)."""

    def __init__(self, path=None):
        self.path = path or os.path.join(STATE_DIR, KEYFILE)
        self.keys = {}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                self.keys = raw.get("keys", {}) or {}
        return self.keys

    def save(self):
        d = os.path.dirname(self.path) or "."
        if not os.path.isdir(d):
            os.makedirs(d, 0o700)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"v": VERSION, "keys": self.keys}, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def create(self, name):
        sk, pk = keypair()
        kid = key_id(pk)
        self.keys[kid] = {"name": name, "public": pk.hex(), "secret": sk.hex()}
        self.save()
        return kid

    def public_map(self):
        return {k: bytes.fromhex(v["public"]) for k, v in self.keys.items()}

    def secret(self, kid):
        return bytes.fromhex(self.keys[kid]["secret"])


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(prog="python3 backend/envelope.py")
    sub = ap.add_subparsers(dest="cmd")
    p_k = sub.add_parser("keygen")
    p_k.add_argument("name", nargs="?", default="controller")
    sub.add_parser("list")
    p_s = sub.add_parser("sign")
    p_s.add_argument("kid")
    sub.add_parser("verify")
    args = ap.parse_args(argv)

    kr = Keyring()

    if args.cmd == "keygen":
        kid = kr.create(args.name)
        print("kid      :", kid)
        print("public   :", kr.keys[kid]["public"])
        print("secret   : disimpan di", kr.path, "(chmod 600)")
        return 0

    if args.cmd == "list":
        if not kr.keys:
            print("(kosong)")
        for kid, v in sorted(kr.keys.items()):
            print("%s  %-16s secret=%s" % (kid, v.get("name", ""), "ya" if v.get("secret") else "tidak"))
        return 0

    if args.cmd == "sign":
        payload = json.loads(sys.stdin.read() or "{}")
        env = sign_envelope(payload, kr.secret(args.kid), kid=args.kid)
        print(json.dumps(env, sort_keys=True))
        return 0

    if args.cmd == "verify":
        env = json.loads(sys.stdin.read())
        ok, reason, payload = verify_envelope(env, kr.public_map())
        print("VERIFY:", "OK" if ok else "GAGAL", "(", reason, ")")
        if ok:
            print("payload:", json.dumps(payload, sort_keys=True))
        return 0 if ok else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
