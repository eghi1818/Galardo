#!/usr/bin/env python3
"""Tes offline backend/bus.py (fail-open, tanpa broker NATS)."""
import os, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import bus

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


os.environ.pop("GALARDO_NATS_URL", None)
bus.reset()

print("== A. subject ==")
check("A prefix benar", bus.subject("job.failed") == "galardo.events.job.failed", bus.subject("job.failed"))
check("A event kosong -> unknown", bus.subject("") == "galardo.events.unknown", bus.subject(""))
check("A event None -> unknown", bus.subject(None) == "galardo.events.unknown")

print("== B. nonaktif -> no-op ==")
check("B enabled() False", bus.enabled() is False)
ok, info = bus.publish("job.failed", {"a": 1})
check("B publish balas False", ok is False, ok)
check("B info 'nats nonaktif'", info == "nats nonaktif", info)
check("B stat skipped naik", bus.stats()["skipped"] >= 1, bus.stats())
check("B tidak ada published", bus.stats()["published"] == 0, bus.stats())

print("== C. aktif tapi broker mati -> fail-open ==")
os.environ["GALARDO_NATS_URL"] = "nats://127.0.0.1:4299"
bus.reset()
check("C enabled() True", bus.enabled() is True)
ok2, info2 = bus.publish("safety.abort", {"b": 2})
check("C publish tidak melempar", isinstance(ok2, bool), ok2)
check("C gagal tercatat / sukses", ok2 in (True, False), ok2)
check("C info berupa string", isinstance(info2, str) and bool(info2), info2)
check("C stats punya last_error bila gagal",
      ok2 is True or bool(bus.stats().get("last_error")), bus.stats())

print("== D. payload tidak mematikan ==")
for payload in ({}, {"x": [1, 2]}, {"n": None}):
    r = bus.publish("uji", payload)
    check("D payload %r aman" % (payload,), isinstance(r, tuple) and len(r) == 2, r)

print("== E. reset ==")
bus.reset()
check("E reset membersihkan klien", bus._CLIENT is None)

os.environ.pop("GALARDO_NATS_URL", None)
print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
