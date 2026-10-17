"""Aturan alerting: event -> hook tertentu, dengan filter field/value.

Beda dari webhook (siaran ke semua hook yang berlangganan event), alerting memilih
tujuan berdasarkan aturan. Fail-open: error tidak menghalangi state machine.
"""
from __future__ import annotations

import threading

COLLECTION = "alert_rules"


def _db(store=None):
    if store is not None:
        return store
    import db
    return db


def _event_types():
    import webhooks
    return webhooks.EVENT_TYPES


def add(event, hook_id, field=None, value=None, note="", actor="system", store=None):
    s = _db(store)
    if event != "*" and event not in _event_types():
        return None, "event tidak dikenal: %s" % event
    if not s.get("webhooks", hook_id):
        return None, "hook tidak ada: %s" % hook_id
    import webhooks
    doc = {"id": webhooks.gen_id("alr"),
           "event": event, "hook_id": hook_id, "field": field or None,
           "value": value if value is not None else "*", "note": note or "",
           "enabled": True}
    return s.insert(COLLECTION, doc, actor=actor, action="alert.rule_added"), None


def list_rules(store=None):
    return list(_db(store).list(COLLECTION))


def remove(rule_id, store=None):
    s = _db(store)
    if not s.get(COLLECTION, rule_id):
        return False
    s.delete(COLLECTION, rule_id)
    return True


def matching(event_type, payload, store=None):
    out = []
    for r in _db(store).list(COLLECTION):
        if not r.get("enabled", True):
            continue
        if r.get("event") not in (event_type, "*"):
            continue
        f = r.get("field")
        if f:
            want = str(r.get("value"))
            got = str((payload or {}).get(f))
            if want != "*" and want != got:
                continue
        out.append(r)
    return out


def run(event_type, payload, store=None):
    """Kirim event ke hook sesuai aturan. Kembalikan (jumlah, error pertama)."""
    try:
        import webhooks
    except Exception as exc:
        return 0, "webhooks tidak bisa diimpor: %s" % exc
    s = _db(store)
    n, err = 0, None
    for r in matching(event_type, payload, store=store):
        hook = s.get("webhooks", r.get("hook_id"))
        if not hook:
            continue
        try:
            did = webhooks.gen_id("dlv")
            threading.Thread(target=webhooks._deliver,
                             args=(hook, event_type, payload, did),
                             daemon=True, name="alert-" + str(r.get("id"))).start()
            n += 1
        except Exception as exc:
            err = err or ("%s: %s" % (type(exc).__name__, exc))
    return n, err
