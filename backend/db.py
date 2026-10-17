"""GALARDO - JSON persistence + append-only audit log.

PostgreSQL is the production source of truth per Technical Design §4; this
MVP uses an atomic-write JSON store with the same collection shapes.
Audit events are appended to data/audit.jsonl (append-only) and mirrored
into the audit_logs collection for API reads.
"""
import json
import os
import threading

from util import now_iso, gen_id, sha256_text

import db_pg  # adapter PostgreSQL (STEP-72); fail-open bila tidak dipakai

LOCK = threading.RLock()
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("GALARDO_DATA_DIR", os.path.join(BASE, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "state.json")
AUDIT_PATH = os.path.join(DATA_DIR, "audit.jsonl")

_state = None


_state_mtime = 0.0


def _load():
    global _state, _state_mtime
    with LOCK:
        if _state is None and _pg_mode():
            st = db_pg.hydrate()
            if st is not None:
                _state = st
                _state_mtime = float("inf")  # file JSON = cermin, bukan sumber
                return _state
        # multi-process coherence: reload when another process wrote the file
        try:
            mtime = os.path.getmtime(DB_PATH) if os.path.exists(DB_PATH) else 0.0
        except OSError:
            mtime = 0.0
        if (_state is not None and mtime and mtime != _state_mtime
                and mtime > _state_mtime and _state_mtime != float("inf")):
            try:
                with open(DB_PATH, "r", encoding="utf-8") as f:
                    _state = json.load(f)
                _state_mtime = mtime
            except (json.JSONDecodeError, OSError):
                pass  # keep in-memory state on transient read issues
        if _state is None:
            os.makedirs(DATA_DIR, exist_ok=True)
            if os.path.exists(DB_PATH):
                with open(DB_PATH, "r", encoding="utf-8") as f:
                    _state = json.load(f)
                _state_mtime = os.path.getmtime(DB_PATH)
            else:
                _state = {}
                _state_mtime = 0.0
        return _state


def _save():
    global _state_mtime
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_state, f, indent=1, default=str)
    os.replace(tmp, DB_PATH)
    try:
        _state_mtime = float("inf") if _pg_mode() else os.path.getmtime(DB_PATH)
    except OSError:
        pass


def col(name):
    s = _load()
    if name not in s:
        s[name] = {}
    return s[name]


def insert(name, doc, actor="system", action=None, resource_type=None, reason="", correlation_id=None):
    with LOCK:
        c = col(name)
        c[doc["id"]] = doc
        if action:
            audit_event(actor, action, resource_type or name, doc["id"], reason, correlation_id,
                        after_hash=sha256_text(json.dumps(doc, sort_keys=True, default=str)))
        _save()
        if _pg_mode():
            db_pg.put(name, doc["id"], doc)
        return doc


def get(name, doc_id):
    with LOCK:
        return col(name).get(doc_id)


def update(name, doc_id, mutate, actor="system", action=None, resource_type=None,
           reason="", correlation_id=None, audit=True):
    with LOCK:
        c = col(name)
        doc = c.get(doc_id)
        if doc is None:
            return None
        before = json.dumps(doc, sort_keys=True, default=str) if (audit and action) else None
        mutate(doc)
        doc["updated_at"] = now_iso()
        if audit and action:
            after = json.dumps(doc, sort_keys=True, default=str)
            audit_event(actor, action, resource_type or name, doc_id, reason, correlation_id,
                        before_hash=sha256_text(before), after_hash=sha256_text(after))
        _save()
        if _pg_mode():
            db_pg.put(name, doc["id"], doc)
        return doc


def delete(name, doc_id, actor="system", action=None, reason=""):
    with LOCK:
        c = col(name)
        if doc_id in c:
            del c[doc_id]
            if action:
                audit_event(actor, action, name, doc_id, reason)
            _save()
            if _pg_mode():
                db_pg.drop(name, doc_id)
            return True
        return False


def list(name, filt=None):
    with LOCK:
        out = [*col(name).values()]
    if filt:
        out = [d for d in out if filt(d)]
    return out


def audit_event(actor, action, resource_type, resource_id, reason="", correlation_id=None,
                before_hash=None, after_hash=None, extra=None):
    ev = {
        "event_id": gen_id("aud"),
        "occurred_at": now_iso(),
        "org_id": "org-lab",
        "actor_id": actor,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "reason": reason or "",
        "correlation_id": correlation_id,
        "before_hash": before_hash,
        "after_hash": after_hash,
    }
    if extra:
        ev["extra"] = extra
    with LOCK:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, default=str) + "\n")
        c = col("audit_logs")
        c[ev["event_id"]] = ev
        _save()
    if _pg_mode():
        db_pg.audit(ev)
    return ev


def observation(job_id, source, severity, description, metric_snapshot=None, correlation_id=None):
    """Append an observation (probe / safety / worker / operator events)."""
    obs = {
        "id": gen_id("obs"),
        "job_id": job_id,
        "source": source,
        "severity": severity,  # INFO | WARN | CRIT
        "observed_at": now_iso(),
        "description": description,
        "metric_snapshot_json": metric_snapshot or {},
        "correlation_id": correlation_id,
    }
    with LOCK:
        c = col("observations")
        c[obs["id"]] = obs
        _save()
        if _pg_mode():
            db_pg.put("observations", obs["id"], obs)
    return obs


def _pg_mode():
    """True bila adapter PG ada dan koneksinya hidup."""
    return db_pg.active()


def all(name, filt=None):
    """Alias list() - dipakai backend/rbac.py:45."""
    return list(name, filt)


def backend():
    """Status backend penyimpanan (untuk /health atau diagnosis)."""
    st = db_pg.status()
    st["mode"] = "postgres" if st.get("active") else "json"
    return st
