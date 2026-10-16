#!/usr/bin/env python3
"""Uji atribusi lapisan. Stdlib only, tanpa jaringan."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "backend")))

import layer_attrib as la   # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


CF = {"cf-ray": "abc123", "server": "cloudflare"}
AK = {"server": "AkamaiGHost", "x-akamai-request-id": "1"}

print("== A. sisi kita vs target ==")
r = la.classify({"http": {"ok": True, "status": 200}}, control_ok=False)
check("A kontrol gagal -> layer ours", r["layer"] == "ours", r)
check("A ours bukan down", r["is_down"] is False, r)
check("A saran menyebut kontrol", "KONTROL" in r["tier_hint"], r["tier_hint"])

print("== B. DNS ==")
r = la.classify({"dns": {"ok": False, "rcode": "NXDOMAIN"}})
check("B NXDOMAIN -> layer dns", r["layer"] == "dns", r)
check("B dns dihitung down", r["is_down"] is True, r)
check("B saran menyebut resolver", "resolver" in r["tier_hint"], r["tier_hint"])

print("== C. origin vs edge (TCP) ==")
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": False, "error": "connection refused"}})
check("C tcp gagal tanpa CDN -> origin", r["layer"] == "origin", r)
r = la.classify({"dns": {"ok": True},
                 "tcp": {"ok": False, "error": "connection refused"},
                 "http": {"headers": CF}})
check("C tcp gagal dengan CDN -> edge", r["layer"] == "edge", r)
check("C CDN terdeteksi", r["cdn"] == "cloudflare", r["cdn"])

print("== D. TLS ==")
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": True},
                 "tls": {"ok": False, "error": "certificate expired"}})
check("D tls gagal tanpa CDN -> origin", r["layer"] == "origin", r)
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": True},
                 "tls": {"ok": False, "error": "handshake"},
                 "http": {"headers": AK}})
check("D tls gagal dengan CDN -> edge", r["layer"] == "edge", r)
check("D CDN akamai terdeteksi", r["cdn"] == "akamai", r["cdn"])

print("== E. HTTP status ==")
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": True}, "tls": {"ok": True},
                 "http": {"ok": False, "status": 503}})
check("E 503 tanpa CDN -> origin", r["layer"] == "origin", r)
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": True}, "tls": {"ok": True},
                 "http": {"ok": False, "status": 503, "headers": AK}})
check("E 503 dengan CDN -> edge", r["layer"] == "edge", r)
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": True}, "tls": {"ok": True},
                 "http": {"ok": False, "status": 404}})
check("E 404 -> app", r["layer"] == "app", r)
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": True}, "tls": {"ok": True},
                 "http": {"ok": True, "status": 200}})
check("E 200 -> healthy", r["layer"] == "healthy", r)
check("E healthy bukan down", r["is_down"] is False, r)

print("== F. timeout ==")
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": True},
                 "http": {"ok": False, "error": "timed out"}})
check("F timeout tanpa CDN -> origin", r["layer"] == "origin", r)
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": True},
                 "http": {"ok": False, "error": "timed out", "headers": CF}})
check("F timeout dengan CDN -> edge", r["layer"] == "edge", r)

print("== G. keyakinan ==")
r = la.classify({"dns": {"ok": True}, "tcp": {"ok": True}, "tls": {"ok": True},
                 "http": {"ok": False, "status": 502}})
check("G 4 sinyal -> keyakinan high", r["confidence"] == "high", r["confidence"])
r = la.classify({"http": {"ok": False, "status": 502}})
check("G 1 sinyal -> keyakinan low", r["confidence"] == "low", r["confidence"])

print("== H. tidak cukup bukti ==")
r = la.classify({})
check("H obs kosong -> unknown", r["layer"] == "unknown", r)
r = la.classify({"cdn": "cloudflare"})
check("H hanya cdn -> unknown", r["layer"] == "unknown", r)
check("H unknown bukan down", r["is_down"] is False, r)

print("== I. saran tindakan ==")
check("I saran edge menyebut T1/T2/T3", "T1" in la.tier_hint("edge"), la.tier_hint("edge"))
check("I saran origin menyebut direct-to-origin",
      "direct-to-origin" in la.tier_hint("origin"), la.tier_hint("origin"))
check("I saran app menyebut assertions",
      "assertions" in la.tier_hint("app"), la.tier_hint("app"))
check("I layer asing -> saran unknown",
      la.tier_hint("ngawur") == la.tier_hint("unknown"), la.tier_hint("ngawur"))

print("== J. summarize ==")
s = la.summarize(la.classify({"dns": {"ok": False, "rcode": "SERVFAIL"}}))
check("J summarize memuat lapisan dan saran",
      "lapisan=dns" in s and "saran:" in s, s)
check("J summarize tahan input aneh", la.summarize(None) == "atribusi tidak tersedia")
check("J LAYERS memuat semua lapisan yang dipakai",
      set(["ours", "dns", "edge", "origin", "app", "healthy", "unknown"]) == set(la.LAYERS), la.LAYERS)
check("J DOWN_LAYERS konsisten dengan LAYERS",
      all(l in la.LAYERS for l in la.DOWN_LAYERS) and "healthy" not in la.DOWN_LAYERS, la.DOWN_LAYERS)

print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
