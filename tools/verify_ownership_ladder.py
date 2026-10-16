#!/usr/bin/env python3
"""Verifikasi tangga kepemilikan (Fase A). Stdlib only, server lokal."""
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

import ownership_ladder as ol   # noqa: E402

PASS = 0
FAIL = 0
TOKEN = "glr-uji-abc123"
ACCOUNT = "usr-operator"
DOMAIN = "contoh.test"


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


class Site(BaseHTTPRequestHandler):
    well_known_value = None
    echo_meta = False
    echo_header = False

    def log_message(self, *a):
        pass

    def _send(self, code, body, extra=None):
        self.send_response(code)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/.well-known/galardo-%s.txt" % TOKEN:
            if Site.well_known_value is None:
                return self._send(404, b"nope")
            return self._send(200, Site.well_known_value.encode(),
                              {"Content-Type": "text/plain"})
        if self.path == "/":
            extra = {}
            if Site.echo_header:
                extra["X-Galardo-Verify"] = TOKEN
            body = b"<html><head>"
            if Site.echo_meta:
                body += ('<meta name="galardo-verify" content="%s">'
                         % TOKEN).encode()
            body += b"</head><body>hai</body></html>"
            return self._send(200, body, extra)
        return self._send(404, b"nope")


srv = ThreadingHTTPServer(("127.0.0.1", 0), Site)
PORT = srv.server_address[1]
BASE = "http://127.0.0.1:%d" % PORT
threading.Thread(target=srv.serve_forever, daemon=True).start()

wk = ol.WellKnownChallenge(DOMAIN, ACCOUNT, token=TOKEN, base_url=BASE)
ec = ol.EchoChallenge(DOMAIN, ACCOUNT, token=TOKEN, base_url=BASE)

print("== A. rung well-known ==")
Site.well_known_value = "galardo-verify=%s:%s" % (ACCOUNT, TOKEN)
p = ol.verify_well_known(wk)
check("A token benar -> ok", p.ok is True, p.to_dict())
check("A method dan rank", p.method == "well_known_file" and p.rank == 3, p.method)
check("A url challenge benar", wk.url == BASE + "/.well-known/galardo-%s.txt" % TOKEN, wk.url)

Site.well_known_value = "galardo-verify=lain:tokenlain"
p = ol.verify_well_known(wk)
check("A token salah -> gagal", p.ok is False, p.evidence)

Site.well_known_value = None
p = ol.verify_well_known(wk)
check("A 404 -> gagal", p.ok is False and p.evidence.get("status") == 404, p.evidence)

print("== B. rung http echo ==")
Site.echo_meta = True
p = ol.verify_http_echo(ec)
check("B meta token -> ok", p.ok is True, p.evidence)

Site.echo_meta = False
Site.echo_header = True
p = ol.verify_http_echo(ec)
check("B header token -> ok", p.ok is True, p.evidence)

Site.echo_header = False
p = ol.verify_http_echo(ec)
check("B tanpa token -> gagal", p.ok is False, p.evidence)

print("== C. rung attestasi ==")
ap = ol.attest(DOMAIN, ACCOUNT, ttl_seconds=3600, note="uji")
check("C ok tapi BUKAN bukti", ap.ok is True and ap.is_proof is False, ap.to_dict())
check("C rank 1", ap.rank == 1, ap.rank)
ap0 = ol.attest(DOMAIN, ACCOUNT, ttl_seconds=0, now=time.time() - 10)
check("C kedaluwarsa terdeteksi", ap0.expired() is True, ap0.expires_at)
check("C belum kedaluwarsa", ap.expired() is False, ap.expires_at)

print("== D. fail-closed / tingkat bukti ==")
check("D attestasi < min well_known_file", ap.sufficient("well_known_file") is False, ap.to_dict())
check("D attestasi >= min attestation", ap.sufficient("operator_attestation") is True)
dp = ol.LadderProof(True, "dns_txt", DOMAIN, ACCOUNT, token=TOKEN)
check("D dns_txt >= min well_known_file", dp.sufficient("well_known_file") is True, dp.to_dict())
check("D gagal -> selalu tidak cukup",
      ol.LadderProof(False, "dns_txt", DOMAIN, ACCOUNT).sufficient("operator_attestation") is False)
try:
    ol.OwnershipLadder(min_level="tidak_ada")
    check("D min_level asing ditolak", False, "tidak melempar")
except ol.LadderError:
    check("D min_level asing ditolak", True)

print("== E. orkestrasi dan injeksi ==")
Site.well_known_value = None
Site.echo_meta = True
Site.echo_header = False
lad = ol.OwnershipLadder(min_level="http_echo")
p = lad.run({"well_known_file": wk, "http_echo": ec})
check("E run() lompat ke rung berikutnya", p.ok is True and p.method == "http_echo", p.method)

ok_gate, why = lad.gate(p)
check("E gate lolos saat cukup", ok_gate is True, why)
Site.echo_meta = False
p_fail = lad.run({"well_known_file": wk, "http_echo": ec})
ok_gate2, why2 = lad.gate(p_fail)
check("E gate menolak saat gagal", ok_gate2 is False, why2)

lad_strict = ol.OwnershipLadder(min_level="dns_txt")
ok_gate3, why3 = lad_strict.gate(ol.attest(DOMAIN, ACCOUNT))
check("E gate menolak attestasi bila min dns_txt", ok_gate3 is False, why3)

calls = []


def fake(url, timeout=6.0):
    calls.append(url)
    return {"status": 200, "headers": {}, "body": b"galardo-verify=usr-operator:" + TOKEN.encode()}


Site.well_known_value = "galardo-verify=%s:%s" % (ACCOUNT, TOKEN)
p = ol.verify_well_known(wk, fetcher=fake)
check("E fetcher bisa disuntik", p.ok is True and len(calls) == 1, p.evidence)

bad = ol.WellKnownChallenge(DOMAIN, ACCOUNT, token=TOKEN, base_url="http://127.0.0.1:1")
p = ol.verify_well_known(bad)
check("E koneksi gagal -> gagal bersih", p.ok is False and p.evidence.get("status") == 0, p.evidence)

print("== F. sidik jari dan urutan ==")
f1 = ol.LadderProof(True, "http_echo", DOMAIN, ACCOUNT, token=TOKEN).fingerprint()
f2 = ol.LadderProof(True, "http_echo", DOMAIN, ACCOUNT, token=TOKEN).fingerprint()
f3 = ol.LadderProof(True, "dns_txt", DOMAIN, ACCOUNT, token=TOKEN).fingerprint()
check("F fingerprint stabil", f1 == f2, f1)
check("F fingerprint beda antar method", f1 != f3, (f1, f3))
check("F LEVELS terurut kuat ke lemah",
      list(ol.LEVELS) == sorted(ol.LEVELS, key=lambda m: -ol.LEVEL_RANK[m]), ol.LEVELS)
check("F adapt_dns_proof membawa rank 4",
      ol.adapt_dns_proof(type("P", (), {"ok": True, "token": TOKEN, "evidence": {}, "label": "_galardo"})(),
                         DOMAIN, ACCOUNT).rank == 4)

srv.shutdown()

print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
