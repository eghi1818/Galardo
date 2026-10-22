#!/usr/bin/env python3
"""Item 10: kunci rantai kepemilikan DNS TXT (backend/ownership.py) + lapisan dns.

Offline penuh - netdns.txt_quorum di-monkeypatch sehingga tidak menyentuh jaringan.
- A primitif: record_name, expected_value, normalisasi domain
- B Challenge: round-trip, TTL, kedaluwarsa, instructions, bump
- C OwnershipVerifier.verify: quorum ok, label cadangan, gagal, kedaluwarsa
- D revoke
- E layer_attrib.classify: ranting dns (NXDOMAIN -> layer dns)
- F wiring endpoint /targets/*/verify/dns
Stdlib only. Exit 1 bila ada yang gagal.
"""
import inspect, os, re, sys, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import ownership as own  # noqa: E402
import layer_attrib as la  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


print("== A. primitif ==")
ch0 = own.Challenge("koler.space", "acc-1", token="tok123")
check("A record_name label utama", own.record_name("koler.space") == "_galardo.koler.space")
check("A record_name label warisan",
      own.record_name("koler.space", own.LEGACY_LABEL) == "_galodo.koler.space")
check("A expected_value format", ch0.expected_value == "galardo-verify=acc-1:tok123", ch0.expected_value)
check("A domain dinormalkan", own.Challenge("Koler.SPACE.", "a").domain == "koler.space")
check("A token baru punya prefix", own.new_token("galardo").startswith("galardo-"))
try:
    own.Challenge("localhost", "a")
    check("A domain tanpa titik ditolak", False, "tidak melempar")
except own.OwnershipError:
    check("A domain tanpa titik ditolak", True)

print("== B. Challenge ==")
ch1 = own.Challenge.from_dict(ch0.to_dict())
check("B round-trip domain/token/attempts",
      (ch1.domain, ch1.token, ch1.attempts) == (ch0.domain, ch0.token, ch0.attempts))
check("B ttl_seconds positif", ch0.ttl_seconds > 0, ch0.ttl_seconds)
check("B belum kedaluwarsa", ch0.is_expired() is False)
ch_exp = own.Challenge("koler.space", "a", created_at=time.time() - own.CHALLENGE_TTL - 10)
check("B kedaluwarsa terdeteksi", ch_exp.is_expired() is True)
check("B instructions memuat nama record & nilai",
      ch0.record_name in "\n".join(ch0.instructions())
      and ch0.expected_value in "\n".join(ch0.instructions()))
check("B bump menaikkan attempts", ch0.bump() == 1 and ch0.bump() == 2, ch0.attempts)

print("== C. OwnershipVerifier.verify (quorum di-monkeypatch) ==")
asli = own.netdns.txt_quorum
dipanggil = []


def palsu(ok_label):
    def f(name, token, resolvers, required, timeout, allow_doh):
        label = name.split(".")[0]
        dipanggil.append((label, token, required))
        if label in ok_label:
            return True, {"quorum": list(resolvers), "value": token}
        return False, {"error": "nxdomain", "resolvers": list(resolvers)}
    return f


try:
    own.netdns.txt_quorum = palsu({"_galardo"})
    ch = own.Challenge("koler.space", "acc-9")
    p = own.OwnershipVerifier().verify(ch)
    check("C quorum ok -> Proof ok", p.ok is True, p.to_dict())
    check("C label terpakai & record tercatat", p.label == "_galardo" and p.record == ch.record_name, p.label)
    check("C verified_at & proof tersimpan", ch.verified_at is not None and ch.proof is not None)
    check("C attempts naik sekali", ch.attempts == 1, ch.attempts)
    check("C fingerprint 64 hex", re.fullmatch(r"[0-9a-f]{64}", p.fingerprint()) is not None, p.fingerprint())

    own.netdns.txt_quorum = palsu({"_galodo"})
    ch2 = own.Challenge("koler.space", "acc-9")
    p2 = own.OwnershipVerifier().verify(ch2)
    check("C label cadangan dipakai bila utama gagal", p2.ok is True and p2.label == "_galodo", p2.label)

    own.netdns.txt_quorum = palsu(set())
    ch3 = own.Challenge("koler.space", "acc-9")
    p3 = own.OwnershipVerifier().verify(ch3)
    check("C semua label gagal -> ok False", p3.ok is False, p3.to_dict())
    check("C evidence memuat percobaan tiap label",
          set((p3.evidence.get("attempts") or {}).keys()) == set(own.DEFAULT_LABELS), p3.evidence)

    ch4 = own.Challenge("koler.space", "acc-9", created_at=time.time() - own.CHALLENGE_TTL - 5)
    p4 = own.OwnershipVerifier().verify(ch4)
    check("C kedaluwarsa -> ok False + alasan",
          p4.ok is False and p4.evidence.get("error") == "challenge expired", p4.evidence)
    check("C kedaluwarsa tidak menaikkan attempts", ch4.attempts == 0, ch4.attempts)
finally:
    own.netdns.txt_quorum = asli

check("C token diteruskan ke txt_quorum", all(r[1] for r in dipanggil), dipanggil[:2])
check("C required=2 diteruskan", all(r[2] == 2 for r in dipanggil), dipanggil[:2])

print("== D. revoke ==")
ch5 = own.Challenge("koler.space", "a")
ch5.verified_at = time.time()
ch5.proof = {"ok": True}
own.OwnershipVerifier().revoke(ch5)
check("D revoke membersihkan verified_at & proof", ch5.verified_at is None and ch5.proof is None)

print("== E. layer_attrib: ranting dns ==")
print("  sig classify:", inspect.signature(la.classify) if hasattr(la, "classify") else "TIDAK ADA")


def klas(obs):
    for args in ((obs,), (obs, None), (obs, None, None)):
        try:
            return la.classify(*args)
        except TypeError:
            continue
    raise TypeError("signature classify tidak dikenal")


r = klas({"dns": {"ok": False, "rcode": "NXDOMAIN"}})
check("E dns gagal -> layer dns", r.get("layer") == "dns", r)
check("E alasan terisi", bool(r.get("reason")), r.get("reason"))
r2 = klas({"dns": {"ok": True, "rcode": "NOERROR"}, "http": {"ok": True, "status": 200}})
check("E dns ok -> bukan layer dns", r2.get("layer") != "dns", r2)

print("== F. wiring endpoint ==")
api = open(os.path.join(ROOT, "backend", "api.py"), encoding="utf-8").read()
check("F endpoint /targets/*/verify/dns ada", '"/targets/*/verify/dns"' in api)
check("F memakai OwnershipVerifier().verify", "_own.OwnershipVerifier().verify(" in api)
check("F menandai dns_txt_quorum saat proof.ok", "dns_txt_quorum" in api)
check("F menandai dns_txt_pending saat gagal", "dns_txt_pending" in api)
check("F menyimpan ownership_proof", '"ownership_proof"' in api)
check("F 422 saat challenge belum ada", "422" in api and "ownership_challenge" in api)

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
