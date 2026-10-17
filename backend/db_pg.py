"""GALARDO - adapter PostgreSQL untuk backend/db.py (STEP-72).

Aturan main:
- Aktif HANYA bila GALARDO_PG_DSN diisi DAN koneksi + DDL berhasil.
- Error apa pun (connect, DDL, query) -> fail-open: db.py tetap memakai JSON.
- Audit SELALU ditulis ke data/audit.jsonl oleh db.py; di mode PG juga dimirror
  ke tabel galardo_audit.
- Saat PG aktif, PostgreSQL = sumber kebenaran; file JSON tetap ditulis sebagai
  cermin supaya tooling lama yang membaca file tidak rusak.

Bentuk dokumen tidak berubah: satu baris = satu dokumen utuh (jsonb), kunci
(collection, id). Ini menghormati API db.update(name, id, mutate) yang bekerja
pada dokumen utuh lewat callable.
"""
import json
import os
import threading

import pg

LOCK = threading.RLock()
TABEL = "galardo_docs"
TABEL_AUDIT = "galardo_audit"
_sock = None
_ready = False
_reason = "belum dicoba"


def enabled():
    """True bila GALARDO_PG_DSN terisi (belum berarti koneksinya hidup)."""
    return bool((os.environ.get(pg.DSN_ENV) or "").strip())


def esc(v):
    return str(v).replace("'", "''")


def status():
    """Status adapter. MEMICU percobaan koneksi (dipakai db.backend()/health)."""
    act = active()
    with LOCK:
        return {"enabled": enabled(), "active": act, "reason": _reason,
                "table": TABEL}


def _rows(conn, sql):
    """Baris hasil query; MELEMPAR bila PG melaporkan error.

    pg.PG.query() mengembalikan (rows, error) dan TIDAK pernah melempar sendiri,
    jadi error wajib diperiksa di sini supaya _call() bisa fail-open.
    """
    res = conn.query(sql)
    if isinstance(res, tuple) and len(res) == 2:
        rows, err = res
    else:
        rows, err = res, None
    if err:
        raise RuntimeError("query: %s" % (err.get("M") if isinstance(err, dict) else err))
    return list(rows or [])


def _dicts(conn, sql, cols):
    out = []
    for row in _rows(conn, sql):
        if isinstance(row, dict):
            out.append(row)
        else:
            out.append(dict(zip(cols, row)))
    return out


def _ddl(conn):
    _rows(conn, "create table if not exists %s (collection text not null, id text not null, "
               "doc jsonb not null, updated_at timestamptz not null default now(), "
               "primary key (collection, id))" % TABEL)
    _rows(conn, "create table if not exists %s (event_id text primary key, "
               "occurred_at timestamptz, payload jsonb not null)" % TABEL_AUDIT)


def _connect():
    global _sock, _ready, _reason
    with LOCK:
        if _sock is not None and _ready:
            return _sock
        if not enabled():
            _ready = False
            _reason = "GALARDO_PG_DSN kosong"
            return None
        try:
            sock = pg.connect()
            _ddl(sock)
            _sock = sock
            _ready = True
            _reason = "aktif"
        except Exception as exc:  # fail-open
            _sock = None
            _ready = False
            _reason = "%s: %s" % (type(exc).__name__, exc)
        return _sock


def active():
    return _connect() is not None


def _call(fn):
    """Jalankan operasi PG; error -> fail-open (kembalikan None, catat alasan)."""
    global _sock, _ready, _reason
    conn = _connect()
    if conn is None:
        return None
    try:
        return fn(conn)
    except Exception as exc:
        _reason = "error operasi: %s: %s" % (type(exc).__name__, exc)
        _ready = False
        try:
            conn.close()
        except Exception:
            pass
        _sock = None
        return None


def hydrate():
    """{collection: {id: doc}} dari PG (None bila PG tidak aktif)."""
    def run(conn):
        out = {}
        for row in _dicts(conn, "select collection, id, doc from %s" % TABEL,
                          ["collection", "id", "doc"]):
            doc = row["doc"]
            if isinstance(doc, (str, bytes, bytearray)):
                doc = json.loads(doc)
            out.setdefault(row["collection"], {})[row["id"]] = doc
        return out
    return _call(run)


def put(collection, doc_id, doc):
    js = esc(json.dumps(doc, default=str))
    sql = ("insert into %s (collection, id, doc, updated_at) values ('%s', '%s', '%s'::jsonb, now()) "
           "on conflict (collection, id) do update set doc = excluded.doc, updated_at = now()"
           % (TABEL, esc(collection), esc(doc_id), js))
    return _call(lambda conn: _rows(conn, sql))


def drop(collection, doc_id):
    sql = "delete from %s where collection = '%s' and id = '%s'" % (TABEL, esc(collection), esc(doc_id))
    return _call(lambda conn: _rows(conn, sql))


def audit(ev):
    js = esc(json.dumps(ev, default=str))
    sql = ("insert into %s (event_id, occurred_at, payload) values ('%s', now(), '%s'::jsonb) "
           "on conflict (event_id) do nothing" % (TABEL_AUDIT, esc(ev.get("event_id")), js))
    return _call(lambda conn: _rows(conn, sql))


def reset():
    """Untuk tes: lupakan koneksi."""
    global _sock, _ready, _reason
    with LOCK:
        if _sock is not None:
            try:
                _sock.close()
            except Exception:
                pass
        _sock = None
        _ready = False
        _reason = "belum dicoba"
