#!/usr/bin/env python3
"""P1.4 / STEP-55 - tes offline rantai kepemilikan dns_txt (rank 4).

Tidak menyentuh jaringan: netdns.txt_quorum di-monkeypatch. Stdlib only.
"""
import os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.normpath(os.path.join(HERE, "..")), "backend"))

import netdns
import ownership
import ownership_ladder as ol

PASS, FAIL = 0, 0
DOMAIN, ACCOUNT, TOKEN = "contoh.test", "usr-operator", "glr-uji-abc123"
_real = netdns.txt_quorum


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


def quorum(ok=True, hits=2, seen=None):
    def _q(name, token, resolvers, required, timeout, allow_doh):
        if seen is not None:
            seen.append({"name": name, "token": token, "required": required})
        return bool(ok), {"name": name, "hits": hits if ok else 0, "required": required}
    return _q


def only_legacy(name, token, resolvers, required, timeout, allow_doh):
    return name.startswith("_galodo."), {"name": name}


def boom(name, token, resolvers, required, timeout, allow_doh):
    raise AssertionError("quorum tidak boleh dipanggil")


def ch():
    return ownership.Challenge(DOMAIN, ACCOUNT, token=TOKEN)


print("== A. challenge dan label ==")
c = ch()
check("A record_name pakai label utama", c.record_name == "_galardo.%s" % DOMAIN, c.record_name)
check("A expected_value format baku",
      c.expected_value == "galardo-verify=%s:%s" % (ACCOUNT, TOKEN), c.expected_value)
check("A label legacy diterima", ownership.LEGACY_LABEL in ownership.DEFAULT_LABELS)
check("A record_name bersih dari titik",
      ownership.record_name("contoh.test.", "_galardo") == "_galardo.contoh.test")

print("== B. quorum cukup -> proof nyata ==")
seen = []
netdns.txt_quorum = quorum(ok=True, hits=2, seen=seen)
p = ownership.OwnershipVerifier(required=2, resolvers=["1.1.1.1", "8.8.8.8", "9.9.9.9"]).verify(ch())
check("B proof ok", p.ok is True, p.to_dict())
check("B label tercatat", p.label == "_galardo", p.label)
check("B record tercatat", p.record == "_galardo.%s" % DOMAIN, p.record)
check("B verified_at terisi", p.verified_at is not None)
check("B token diteruskan ke resolver", bool(seen) and seen[0]["token"] == TOKEN, seen)
lp = ol.adapt_dns_proof(p, DOMAIN, ACCOUNT)
check("B adapt -> rank 4", lp.rank == 4, lp.to_dict())
check("B adapt -> method dns_txt", lp.method == "dns_txt", lp.method)
check("B adapt -> is_proof", lp.is_proof is True, lp.to_dict())
g, why = ol.OwnershipLadder(min_level="dns_txt").gate(lp)
check("B gate lolos", g is True, why)
check("B cukup untuk min well_known_file", lp.sufficient("well_known_file") is True)
check("B attestasi tidak cukup untuk dns_txt",
      ol.OwnershipLadder(min_level="dns_txt").gate(ol.attest(DOMAIN, ACCOUNT))[0] is False)

print("== C. quorum tidak cukup -> fail-closed ==")
netdns.txt_quorum = quorum(ok=False, hits=0)
pb = ownership.OwnershipVerifier(required=2).verify(ch())
check("C proof gagal", pb.ok is False, pb.to_dict())
check("C evidence mencatat percobaan per label",
      isinstance(pb.evidence.get("attempts"), dict)
      and set(pb.evidence["attempts"]) == set(["_galardo", "_galodo"]), pb.evidence)
lpb = ol.adapt_dns_proof(pb, DOMAIN, ACCOUNT)
check("C ladder_proof gagal", lpb.ok is False, lpb.to_dict())
gb, whyb = ol.OwnershipLadder(min_level="dns_txt").gate(lpb)
check("C gate menolak", gb is False, whyb)

print("== D. jatuh ke label legacy ==")
netdns.txt_quorum = only_legacy
pl = ownership.OwnershipVerifier(required=2).verify(ch())
check("D lolos lewat label legacy", pl.ok is True and pl.label == "_galodo", pl.to_dict())

print("== E. challenge kedaluwarsa ==")
netdns.txt_quorum = boom
ce = ch()
ce.created_at = time.time() - ownership.CHALLENGE_TTL - 10
pe = ownership.OwnershipVerifier(required=2).verify(ce)
check("E kedaluwarsa -> gagal", pe.ok is False, pe.to_dict())
check("E alasan eksplisit", pe.evidence.get("error") == "challenge expired", pe.evidence)

print("== F. tingkat bukti dan min_level ==")
try:
    ol.OwnershipLadder(min_level="tidak_ada")
    check("F min_level asing ditolak", False, "tidak melempar")
except ol.LadderError:
    check("F min_level asing ditolak", True)
check("F LEVELS terurut kuat ke lemah",
      list(ol.LEVELS) == sorted(ol.LEVELS, key=lambda m: -ol.LEVEL_RANK[m]), ol.LEVELS)

print("== G. sidik jari ==")
f1 = ol.LadderProof(True, "dns_txt", DOMAIN, ACCOUNT, token=TOKEN).fingerprint()
f2 = ol.LadderProof(True, "dns_txt", DOMAIN, ACCOUNT, token=TOKEN).fingerprint()
f3 = ol.LadderProof(True, "well_known_file", DOMAIN, ACCOUNT, token=TOKEN).fingerprint()
check("G stabil", f1 == f2, f1)
check("G beda antar method", f1 != f3, (f1, f3))

netdns.txt_quorum = _real
print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
