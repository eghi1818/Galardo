#!/usr/bin/env python3
"""
verify_trust.py — uji kebijakan kepercayaan, termasuk pembuktian lewat TCP.

  A. Semantik mode off/warn/enforce, replay, tamper, kid tak dikenal, role.
  B. Cache replay (TTL + batas ukuran) dan persistensi PeerStore.
  C. END-TO-END lewat socket TCP sungguhan: server menolak rogue, tamper,
     replay, dan pesan tanpa tanda tangan; balasan server juga ditandatangani
     dan diverifikasi klien.

Exit 0 hanya kalau semua check lolos.
"""

import copy
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend import envelope, trust  # noqa: E402

PASSED = []
FAILED = []


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print("  PASS  " + name)
    else:
        FAILED.append(name)
        print("  FAIL  " + name + ("  <-- " + str(detail) if detail != "" else ""))


def _node(d, name):
    kr = envelope.Keyring(os.path.join(d, name, "keys.json"))
    kid = kr.create(name)
    return kr, kid


def test_modes():
    d = tempfile.mkdtemp(prefix="galardo-trust-")
    try:
        kr, kid = _node(d, "self")
        peers = trust.PeerStore(os.path.join(d, "peers.json"))
        peer_sk, peer_pk = envelope.keypair()
        peer_kid = peers.add(peer_pk, name="peer", role="worker")
        rogue_sk, _rogue_pk = envelope.keypair()

        pol = trust.TrustPolicy(mode="off", keyring=kr, peers=peers)
        ok, reason, payload = pol.unwrap({"hello": "world"})
        check("A off terima payload mentah", ok and reason == "off" and payload == {"hello": "world"}, reason)

        pol = trust.TrustPolicy(mode="warn", keyring=kr, peers=peers)
        ok, reason, payload = pol.unwrap({"hello": "world"})
        check("A warn terima tanpa tanda tangan", ok and reason == "unsigned", reason)
        check("A warn menghitung unsigned", pol.stats["unsigned"] == 1, pol.stats)

        rogue_env = envelope.sign_envelope({"x": 1}, rogue_sk)
        ok, reason, _ = pol.unwrap(rogue_env)
        check("A warn terima kid tak dikenal tapi menandai", ok and reason == "unknown_kid", reason)

        pol = trust.TrustPolicy(mode="enforce", keyring=kr, peers=peers)
        ok, reason, _ = pol.unwrap({"hello": "world"})
        check("A enforce tolak tanpa tanda tangan", (not ok) and reason == "unsigned", reason)
        ok, reason, _ = pol.unwrap(rogue_env)
        check("A enforce tolak kid tak dikenal", (not ok) and reason == "unknown_kid", reason)

        good = envelope.sign_envelope({"x": 1}, peer_sk)
        ok, reason, payload = pol.unwrap(good)
        check("A enforce terima yang sah", ok and reason == "ok" and payload == {"x": 1}, reason)

        ok, reason, _ = pol.unwrap(good)
        check("A enforce tolak replay", (not ok) and reason == "replay", reason)
        check("A replay tercatat", pol.stats["replayed"] == 1, pol.stats)

        bad = copy.deepcopy(good)
        bad["body"]["payload"]["x"] = 2
        ok, reason, _ = pol.unwrap(bad)
        check("A enforce tolak payload diubah", (not ok) and reason == "bad_signature", reason)

        old = envelope.sign_envelope({"x": 1}, peer_sk, ts=time.time() - 5000)
        ok, reason, _ = pol.unwrap(old)
        check("A enforce tolak kedaluwarsa", (not ok) and reason == "stale", reason)

        check("A role worker dikenali", pol.require_role({"body": {"kid": peer_kid}}, "worker"))
        check("A role salah ditolak", not pol.require_role({"body": {"kid": peer_kid}}, "controller"))
        check("A mode off meloloskan role apa pun",
              trust.TrustPolicy(mode="off", keyring=kr, peers=peers).require_role("apa-saja", "controller"))
        check("A mode asing jatuh ke warn",
              trust.TrustPolicy(mode="ngawur", keyring=kr, peers=peers).mode == "warn")

        pol.mode = "enforce"
        pol2 = trust.TrustPolicy(mode="enforce", keyring=kr, peers=peers)
        unsigned_env = pol2.wrap({"no": "key"})
        check("A wrap tanpa secret menghasilkan sig kosong", unsigned_env["sig"] == "", unsigned_env["sig"])
        ok, reason, _ = pol2.unwrap(unsigned_env)
        check("A enforce tolak envelope tanpa sig", (not ok) and reason == "unsigned", reason)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_replaycache_and_peerstore():
    rc = trust.ReplayCache(max_entries=4, ttl=10.0)
    now = 1000.0
    check("B nonce baru diterima", rc.check_and_add("a", now=now))
    check("B nonce sama ditolak", rc.check_and_add("a", now=now) is False)
    for n in ("b", "c", "d", "e"):
        rc.check_and_add(n, now=now)
    check("B batas ukuran memicu pemangkasan", len(rc) <= 6, len(rc))
    check("B hits tercatat", rc.hits == 1, rc.hits)

    rc2 = trust.ReplayCache(max_entries=100, ttl=1.0)
    rc2.check_and_add("old", now=1000.0)
    rc2._prune(now=2000.0, force=True)
    check("B entri kedaluwarsa dipangkas", len(rc2) == 0, len(rc2))

    d = tempfile.mkdtemp(prefix="galardo-peers-")
    try:
        path = os.path.join(d, "peers.json")
        ps = trust.PeerStore(path)
        _sk, pk = envelope.keypair()
        kid = ps.add(pk, name="vps", role="worker")
        check("B peer tersimpan", os.path.exists(path))
        ps2 = trust.PeerStore(path)
        check("B peer muat ulang terlihat", kid in ps2.peers)
        check("B role ikut tersimpan", ps2.role(kid) == "worker")
        check("B public_map benar", ps2.public_map()[kid] == pk)
        check("B peers.json tanpa secret", "secret" not in json.dumps(ps2.peers))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_end_to_end():
    d = tempfile.mkdtemp(prefix="galardo-e2e-")
    srv = None
    try:
        ckr, ckid = _node(d, "controller")
        wkr, wkid = _node(d, "worker")

        cpeers = trust.PeerStore(os.path.join(d, "controller", "peers.json"))
        cpeers.add(bytes.fromhex(wkr.keys[wkid]["public"]), name="worker", role="worker")
        wpeers = trust.PeerStore(os.path.join(d, "worker", "peers.json"))
        wpeers.add(bytes.fromhex(ckr.keys[ckid]["public"]), name="controller", role="controller")

        server_policy = trust.TrustPolicy(mode="enforce", keyring=wkr, peers=wpeers)
        client_policy = trust.TrustPolicy(mode="enforce", keyring=ckr, peers=cpeers)

        class Handler(BaseHTTPRequestHandler):
            policy = server_policy

            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n)
                try:
                    env = json.loads(raw.decode("utf-8"))
                except Exception:
                    env = None
                ok, reason, payload = self.policy.unwrap(env)
                if ok:
                    code, reply = 200, {"echo": payload}
                else:
                    code, reply = 401, {"reason": reason}
                data = json.dumps(self.policy.wrap(reply)).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        srv.daemon_threads = True
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        def post(env):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            data = json.dumps(env).encode("utf-8")
            conn.request("POST", "/msg", data, {"Content-Type": "application/json"})
            r = conn.getresponse()
            body = r.read()
            conn.close()
            return r.status, json.loads(body.decode("utf-8"))

        good = client_policy.wrap({"cmd": "start", "n": 2})
        status, resp = post(good)
        ok, reason, payload = client_policy.unwrap(resp)
        check("C pesan sah diterima (200)", status == 200, status)
        check("C balasan server terverifikasi klien", ok and payload["echo"] == {"cmd": "start", "n": 2}, reason)
        check("C balasan server bertanda tangan", bool(resp.get("sig")))

        rogue_sk, _ = envelope.keypair()
        status, resp = post(envelope.sign_envelope({"cmd": "kill"}, rogue_sk))
        check("C rogue ditolak (401)", status == 401, status)

        tampered = copy.deepcopy(good)
        tampered["body"]["payload"]["n"] = 99
        status, resp = post(tampered)
        check("C tamper ditolak (401)", status == 401, status)

        status, resp = post(good)
        check("C replay ditolak (401)", status == 401, status)

        status, resp = post({"cmd": "ping"})
        check("C tanpa tanda tangan ditolak (401)", status == 401, status)

        check("C penolakan server tercatat", server_policy.stats["rejected"] >= 4, server_policy.stats)

        server_policy.mode = "warn"
        status, resp = post({"cmd": "ping"})
        check("C mode warn menerima tanpa tanda tangan (200)", status == 200, status)
        server_policy.mode = "enforce"

        check("C server memakai kid sendiri saat membalas", resp["body"]["kid"] == wkid, resp["body"]["kid"])
        print("  INFO  " + server_policy.stats_line())
        print("  INFO  " + client_policy.stats_line())
    finally:
        if srv is not None:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(d, ignore_errors=True)


def main():
    print("=" * 62)
    print("  VERIFIKASI TIER 1 — KEBIJAKAN KEPERCAYAAN ANTAR-NODE")
    print("=" * 62)
    print()
    print("--- A. Mode off/warn/enforce + replay + role ---")
    test_modes()
    print()
    print("--- B. Cache replay + persistensi peer ---")
    test_replaycache_and_peerstore()
    print()
    print("--- C. END-TO-END lewat TCP ---")
    test_end_to_end()
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
