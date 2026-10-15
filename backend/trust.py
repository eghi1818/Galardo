"""
trust.py — kebijakan kepercayaan antar-node di atas backend.envelope.

Tiga mode:
  off     : tanpa verifikasi sama sekali (transisi, lab)
  warn    : verifikasi dijalankan, pelanggaran dihitung, tapi tetap diterima
  enforce : envelope tidak sah ATAU tanpa tanda tangan -> ditolak

Pemisahan penyimpanan (penting):
  .galardo/keys.json   -> kunci milik node ini (secret + public), chmod 600
  .galardo/peers.json  -> kunci PUBLIK node lain yang dipercaya (+ role)
Secret node lain tidak pernah ada di peers.json.

Role di peers.json adalah benih RBAC: node hanya boleh mengirim perintah
sesuai perannya. Verifikasi tanda tangan dan otorisasi peran adalah dua
langkah terpisah dan tidak pernah digabung.

Tidak ada payload yang dieksekusi sebelum verifikasi lolos.
"""

import json
import os
import secrets
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend import envelope

MODES = ("off", "warn", "enforce")
DEFAULT_MODE = "warn"
STATE_DIR = envelope.STATE_DIR
PEERFILE = "peers.json"


class ReplayCache:
    """Nonce yang sudah dilihat, dengan pemangkasan berbasis TTL dan batas ukuran."""

    def __init__(self, max_entries=4096, ttl=envelope.DEFAULT_WINDOW * 2):
        self._seen = {}
        self.max_entries = max_entries
        self.ttl = ttl
        self.hits = 0

    def check_and_add(self, nonce, now=None):
        now = time.time() if now is None else now
        if nonce in self._seen:
            self.hits += 1
            return False
        self._seen[nonce] = now
        if len(self._seen) > self.max_entries:
            self._prune(now, force=True)
        return True

    def _prune(self, now, force=False):
        if not force and len(self._seen) <= self.max_entries:
            return
        cut = now - self.ttl
        self._seen = {n: t for n, t in self._seen.items() if t >= cut}

    def __len__(self):
        return len(self._seen)


class PeerStore:
    """Kunci publik node lain yang dipercaya + role. Tanpa secret."""

    def __init__(self, path=None):
        self.path = path or os.path.join(STATE_DIR, PEERFILE)
        self.peers = {}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                self.peers = raw.get("peers", {}) or {}
        return self.peers

    def save(self):
        d = os.path.dirname(self.path) or "."
        if not os.path.isdir(d):
            os.makedirs(d, 0o700)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"v": envelope.VERSION, "peers": self.peers}, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def add(self, public_key, name="", role=""):
        kid = envelope.key_id(public_key)
        self.peers[kid] = {"name": name, "role": role, "public": bytes(public_key).hex()}
        self.save()
        return kid

    def public_map(self):
        return {k: bytes.fromhex(v["public"]) for k, v in self.peers.items()}

    def role(self, kid):
        return self.peers.get(kid, {}).get("role", "")

    def has_secret(self):
        return False


class TrustPolicy:
    """Satu node: kunci sendiri + daftar peer yang dipercaya + mode."""

    def __init__(self, mode=None, keyring=None, peers=None, kid=None,
                 window=envelope.DEFAULT_WINDOW, replay=None):
        self.mode = (mode or os.environ.get("GALARDO_TRUST_MODE") or DEFAULT_MODE).lower()
        if self.mode not in MODES:
            self.mode = DEFAULT_MODE
        self.keyring = keyring if keyring is not None else envelope.Keyring()
        self.peers = peers if peers is not None else PeerStore()
        if kid is None:
            kids = sorted(self.keyring.keys)
            kid = kids[0] if kids else None
        self.kid = kid
        self.window = window
        self.replay = replay if replay is not None else ReplayCache()
        self.stats = {"accepted": 0, "rejected": 0, "unsigned": 0, "warned": 0, "replayed": 0}

    # --- sisi kirim -------------------------------------------------------
    def _secret(self, kid):
        entry = self.keyring.keys.get(kid or "")
        if not entry or not entry.get("secret"):
            return None
        return bytes.fromhex(entry["secret"])

    def wrap(self, payload, kid=None):
        kid = kid or self.kid
        secret = self._secret(kid)
        if secret is None:
            return {"body": {"v": envelope.VERSION, "kid": kid or "",
                             "ts": int(time.time()), "nonce": secrets.token_hex(8),
                             "payload": payload}, "sig": ""}
        return envelope.sign_envelope(payload, secret, kid=kid)

    # --- sisi terima ------------------------------------------------------
    def unwrap(self, env, now=None):
        """Kembalikan (ok, reason, payload). reason selalu terisi."""
        now = time.time() if now is None else now

        if self.mode == "off":
            self.stats["accepted"] += 1
            if isinstance(env, dict) and isinstance(env.get("body"), dict):
                return True, "off", env["body"].get("payload")
            return True, "off", env

        signed = isinstance(env, dict) and isinstance(env.get("body"), dict) and bool(env.get("sig"))

        if signed:
            ok, reason, payload = envelope.verify_envelope(
                env, self.peers.public_map(), window=self.window, now=now)
            if ok:
                nonce = env["body"]["nonce"]
                if not self.replay.check_and_add(nonce, now=now):
                    self.stats["replayed"] += 1
                    if self.mode == "enforce":
                        self.stats["rejected"] += 1
                        return False, "replay", None
                    self.stats["warned"] += 1
                    return True, "replay", payload
                self.stats["accepted"] += 1
                return True, "ok", payload
            self.stats["warned"] += 1
            if self.mode == "enforce":
                self.stats["rejected"] += 1
                return False, reason, None
            return True, reason, env.get("body", {}).get("payload")

        # tanpa tanda tangan
        self.stats["unsigned"] += 1
        if self.mode == "enforce":
            self.stats["rejected"] += 1
            return False, "unsigned", None
        self.stats["warned"] += 1
        if isinstance(env, dict) and isinstance(env.get("body"), dict):
            return True, "unsigned", env["body"].get("payload")
        return True, "unsigned", env

    # --- otorisasi (terpisah dari autentikasi) ----------------------------
    def kid_of(self, env_or_kid):
        if isinstance(env_or_kid, dict):
            body = env_or_kid.get("body") or {}
            return body.get("kid")
        return env_or_kid

    def require_role(self, env_or_kid, role):
        if self.mode == "off":
            return True
        return self.peers.role(self.kid_of(env_or_kid)) == role

    def stats_line(self):
        return ("mode=%s accepted=%d rejected=%d unsigned=%d warned=%d replayed=%d replay_cache=%d"
                % (self.mode, self.stats["accepted"], self.stats["rejected"], self.stats["unsigned"],
                   self.stats["warned"], self.stats["replayed"], len(self.replay)))


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(prog="python3 backend/trust.py")
    sub = ap.add_subparsers(dest="cmd")
    p_add = sub.add_parser("peer-add")
    p_add.add_argument("public_hex")
    p_add.add_argument("name", nargs="?", default="")
    p_add.add_argument("role", nargs="?", default="")
    sub.add_parser("peer-list")
    sub.add_parser("mode")
    sub.add_parser("self")
    args = ap.parse_args(argv)

    peers = PeerStore()

    if args.cmd == "peer-add":
        pk = bytes.fromhex(args.public_hex)
        if len(pk) != 32:
            print("public key harus 32 byte (64 hex)")
            return 1
        kid = peers.add(pk, name=args.name, role=args.role)
        print("peer ditambahkan:", kid, args.name, args.role)
        return 0

    if args.cmd == "peer-list":
        if not peers.peers:
            print("(kosong)")
        for kid, v in sorted(peers.peers.items()):
            print("%s  %-16s role=%-12s %s" % (kid, v.get("name", ""), v.get("role", ""), v["public"][:24]))
        return 0

    if args.cmd == "mode":
        pol = TrustPolicy(peers=peers)
        print("mode efektif:", pol.mode)
        print("dari env GALARDO_TRUST_MODE:", os.environ.get("GALARDO_TRUST_MODE", "(tidak diset)"))
        return 0

    if args.cmd == "self":
        kr = envelope.Keyring()
        for kid, v in sorted(kr.keys.items()):
            print("%s  %-16s public=%s" % (kid, v.get("name", ""), v["public"]))
        if not kr.keys:
            print("(belum ada kunci; jalankan: make keygen)")
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
