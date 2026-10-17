#!/usr/bin/env python3
"""Tes offline alerts.py: aturan, filter, eksekusi (store & _deliver palsu)."""
import os, sys, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import alerts, webhooks

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


class FakeStore(object):
    def __init__(self):
        self.d = {}
        self.n = 0
    def _c(self, name):
        return self.d.setdefault(name, {})
    def insert(self, name, doc, actor=None, action=None):
        self.n += 1
        doc = dict(doc)
        if not doc.get("id"):
            doc["id"] = "id-%d" % self.n
        self._c(name)[doc["id"]] = doc
        return doc
    def get(self, name, _id):
        return self._c(name).get(_id)
    def list(self, name):
        return list(self._c(name).values())
    def delete(self, name, _id):
        return self._c(name).pop(_id, None)


webhooks._deliver = lambda hook, ev, pl, did: SENT.append((hook["id"], ev, did)) or True

st = FakeStore()
st.insert("webhooks", {"id": "h1", "name": "a", "status": "ACTIVE", "events": ["job.failed"]})
st.insert("webhooks", {"id": "h2", "name": "b", "status": "ACTIVE", "events": ["job.failed"]})

print("== A. validasi ==")
r, e = alerts.add("job.failed", "h1", store=st)
check("A tambah aturan sah", r is not None and e is None, e)
check("A id diberikan", (r or {}).get("id") is not None, r)
r2, e2 = alerts.add("event.ngawur", "h1", store=st)
check("A event tak dikenal ditolak", r2 is None and "tidak dikenal" in (e2 or ""), e2)
r3, e3 = alerts.add("job.failed", "h9", store=st)
check("A hook tak ada ditolak", r3 is None and "hook tidak ada" in (e3 or ""), e3)
r4, _ = alerts.add("*", "h2", store=st)
check("A wildcard event diterima", r4 is not None)

print("== B. filter ==")
alerts.add("job.failed", "h1", field="reason_code", value="DOWN_CONFIRMED", store=st)
check("B cocok event tanpa filter", len(alerts.matching("job.failed", {}, store=st)) == 2,
      len(alerts.matching("job.failed", {}, store=st)))
m = alerts.matching("job.failed", {"reason_code": "DOWN_CONFIRMED"}, store=st)
check("B filter cocok menambah aturan", len(m) == 3, len(m))
m2 = alerts.matching("job.failed", {"reason_code": "LAIN"}, store=st)
check("B filter tidak cocok disaring", len(m2) == 2, len(m2))
check("B wildcard ikut cocok", any(x["hook_id"] == "h2" for x in alerts.matching("apa.saja", {}, store=st)))

print("== C. eksekusi ==")
del SENT[:]
n, err = alerts.run("job.failed", {"reason_code": "LAIN"}, store=st)
time.sleep(0.3)
check("C terkirim sesuai aturan", n == 2, n)
check("C _deliver dipanggil", len(SENT) == 2, SENT)
check("C tidak ada error", err is None, err)
del SENT[:]
n2, _ = alerts.run("job.completed", {}, store=st)
time.sleep(0.2)
check("C event lain hanya wildcard", n2 == 1, n2)

print("== D. nonaktif & hapus ==")
rid = alerts.list_rules(store=st)[0]["id"]
st.get("alert_rules", rid)["enabled"] = False
del SENT[:]
alerts.run("job.failed", {}, store=st)
time.sleep(0.2)
check("D aturan nonaktif tidak dikirim", len(SENT) < 3, SENT)
check("D hapus aturan sah", alerts.remove(rid, store=st) is True)
check("D hapus id ngawur -> False", alerts.remove("tidak-ada", store=st) is False)

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
