#!/usr/bin/env python3
"""Tes offline backend/otlp.py: struktur OTLP JSON + fail-open."""
import json, os, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import otlp

PASS = FAIL = 0
SENT = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


def sender(url, body, timeout):
    SENT.append((url, json.loads(body)))


os.environ.pop("GALARDO_OTLP_URL", None)

print("== A. bentuk nilai atribut ==")
check("A bool -> boolValue", otlp._val(True) == {"boolValue": True})
check("A int -> intValue string", otlp._val(7) == {"intValue": "7"})
check("A float -> doubleValue", otlp._val(1.5) == {"doubleValue": 1.5})
check("A str -> stringValue", otlp._val("x") == {"stringValue": "x"})
check("A attrs terurut", [a["key"] for a in otlp._attrs({"b": 1, "a": 2})] == ["a", "b"])

print("== B. struktur metric ==")
m = otlp.metric("galardo.requests", [{"value": 5, "attrs": {"job_id": "j1"}}])
check("B nama", m["name"] == "galardo.requests", m)
check("B gauge ada", "gauge" in m, m)
dp = m["gauge"]["dataPoints"][0]
check("B dataPoint punya timeUnixNano string", isinstance(dp["timeUnixNano"], str), dp)
check("B asInt string", dp["asInt"] == "5", dp)
check("B atribut job_id ada", dp["attributes"][0]["key"] == "job_id", dp)
ms = otlp.metric("galardo.x", [{"value": 2}], kind="sum")
check("B sum punya aggregationTemporality", ms["sum"]["aggregationTemporality"] == 2, ms)

print("== C. struktur payload ==")
pl = otlp.build_metrics([m], resource={"job.id": "j1"})
rm = pl["resourceMetrics"][0]
check("C resourceMetrics ada", "resourceMetrics" in pl)
check("C service.name default", any(a["key"] == "service.name" for a in rm["resource"]["attributes"]),
      rm["resource"]["attributes"])
check("C scopeMetrics + scope name", rm["scopeMetrics"][0]["scope"]["name"] == otlp.SCOPE)
check("C metric ikut", rm["scopeMetrics"][0]["metrics"][0]["name"] == "galardo.requests")
sp = otlp.build_span("job.run", 1, 2, {"job.id": "j1"})
check("C span payload benar",
      sp["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"] == "job.run", sp)
check("C span waktu string",
      isinstance(sp["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["startTimeUnixNano"], str))

print("== D. nonaktif -> no-op ==")
check("D enabled() False", otlp.enabled() is False)
ok, info = otlp.send(pl)
check("D send balas False", ok is False, ok)
check("D info 'otlp nonaktif'", info == "otlp nonaktif", info)
check("D skipped naik", otlp.stats()["skipped"] >= 1, otlp.stats())

print("== E. kirim dengan sender ==")
del SENT[:]
ok2, i2 = otlp.send(pl, url="http://127.0.0.1:4318", sender=sender)
check("E terkirim", ok2 is True, i2)
check("E path /v1/metrics", SENT and SENT[0][0].endswith("/v1/metrics"), SENT)
check("E body JSON sah", SENT and "resourceMetrics" in SENT[0][1], SENT)

print("== F. export_job kirim metrics + span ==")
del SENT[:]
ok3, i3 = otlp.export_job("j9", {"requests": 3, "ok": 3, "lat_sum": 12.5, "catatan": "x"},
                          sender=sender)
check("F sukses", ok3 is True, i3)
check("F dua kiriman (metrics + traces)", len(SENT) == 2, SENT)
check("F ada /v1/traces", any(u.endswith("/v1/traces") for u, _ in SENT), [u for u, _ in SENT])
check("F window non-angka dilewati",
      all(not mm["name"].endswith("catatan") for _, b in SENT for mm in
          b.get("resourceMetrics", [{}])[0].get("scopeMetrics", [{}])[0].get("metrics", [])
          if b.get("resourceMetrics")), SENT)

print("== G. sender yang melempar -> fail-open ==")
def boom(url, body, timeout):
    raise RuntimeError("mati")
ok4, i4 = otlp.send(pl, url="http://x", sender=boom)
check("G tidak melempar", isinstance(ok4, bool), ok4)
check("G gagal tercatat", otlp.stats()["failed"] >= 1, otlp.stats())
check("G last_error terisi", bool(otlp.stats().get("last_error")), otlp.stats())

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
