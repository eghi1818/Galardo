#!/usr/bin/env python3
"""Verifier STEP-72: adapter db -> PostgreSQL dengan fallback JSON (offline)."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  | " + str(detail)))


# --- sandbox data + DSN kosong ---
sand = tempfile.mkdtemp(prefix="galardo72-")
os.makedirs(os.path.join(sand, "data"), exist_ok=True)
for var in ("GALARDO_DATA_DIR", "GALARDO_DATA"):
    os.environ[var] = sand
os.environ.pop("GALARDO_PG_DSN", None)
os.chdir(sand)

import db_pg
import db

print("  ..   DB_PATH =", db.DB_PATH)

# A. permukaan adapter
for fn in ("enabled", "status", "hydrate", "put", "drop", "audit", "reset", "active", "_rows", "_dicts"):
    check("A db_pg.%s ada" % fn, callable(getattr(db_pg, fn, None)))


# B. _rows membaca bentuk balikan NYATA (rows, err) dan melempar saat err
class FakeConn(object):
    def __init__(self, res):
        self.res = res

    def query(self, sql):
        return self.res


ok = FakeConn(([{"id": "u1"}], None))
try:
    rows = db_pg._rows(ok, "select 1")
    check("B _rows membaca tuple (rows, err)", rows == [{"id": "u1"}], rows)
except Exception as exc:
    check("B _rows membaca tuple (rows, err)", False, exc)

bad = FakeConn(([], {"M": "boom"}))
try:
    db_pg._rows(bad, "select 1")
    check("B _rows melempar saat err", False, "tidak melempar")
except Exception as exc:
    check("B _rows melempar saat err", "boom" in str(exc), exc)


# C. _dicts memetakan baris tuple ke kolom
class TupleConn(object):
    def query(self, sql):
        return ([(1, "a")], None)


got = db_pg._dicts(TupleConn(), "x", ["id", "nama"])
check("C _dicts memetakan tuple baris", got == [{"id": 1, "nama": "a"}], got)

# D. esc
check("D esc menggandakan kutip", db_pg.esc("a'b") == "a''b", db_pg.esc("a'b"))

# E. DSN kosong -> tidak aktif + alasan jelas (tanpa melempar)
db_pg.reset()
check("E enabled False saat DSN kosong", db_pg.enabled() is False)
check("E active False saat DSN kosong", db_pg.active() is False, db_pg.status())
check("E reason jelas", "kosong" in db_pg.status()["reason"], db_pg.status())

# F. DSN ada tapi PG mati -> fail-open
os.environ["GALARDO_PG_DSN"] = "postgres://galardo:galardo@127.0.0.1:1/galardo"
db_pg.reset()
check("F enabled True saat DSN ada", db_pg.enabled() is True)
_st = db_pg.status()          # tanpa memanggil active() lebih dulu
check("F status() memicu koneksi sendiri", _st["reason"] != "belum dicoba", _st)
check("F active False saat PG mati", _st["active"] is False, _st)
check("F reason terisi setelah gagal", _st["reason"] not in ("belum dicoba", ""), _st)
os.environ.pop("GALARDO_PG_DSN", None)
db_pg.reset()

# G. bentuk SQL
src = open(os.path.join(BACKEND, "db_pg.py")).read()
check("G DDL create table if not exists x2", src.count("create table if not exists") == 2, src.count("create table if not exists"))
check("G put idempotent", "on conflict (collection, id) do update" in src)
check("G audit idempotent", "on conflict (event_id) do nothing" in src)
check("G tidak ada _raw tersisa", "_raw(" not in src)

# H. db.py: permukaan publik utuh + alias + status
for fn in ("insert", "get", "update", "delete", "list", "col", "audit_event", "observation", "all", "backend"):
    check("H db.%s callable" % fn, callable(getattr(db, fn, None)))
check("H db.all == list", db.all("users") == db.list("users"))
check("H db.backend mode json", db.backend().get("mode") == "json", db.backend())

# I. jalur JSON tetap berfungsi penuh (round-trip)
db.insert("users", {"id": "u-uji", "nama": "budi"})
check("I insert/get", (db.get("users", "u-uji") or {}).get("nama") == "budi")
db.update("users", "u-uji", lambda x: (x.update({"nama": "budi2"}), x)[1])
check("I update", db.get("users", "u-uji")["nama"] == "budi2")
check("I list", any(x.get("id") == "u-uji" for x in db.list("users")))
db.delete("users", "u-uji")
check("I delete", db.get("users", "u-uji") is None)
_variants = [
    ("verifier", "uji.72", "user", "u-uji"),   # (actor, action, resource_type, resource_id)
    ("verifier", "uji.72", "user", "u-uji", "sebab uji"),
    ("uji.72", "uji.72", "user", "u-uji"),
]
_ok = False
for _v in _variants:
    try:
        db.audit_event(*_v)
        _ok = True
        break
    except TypeError:
        continue
check("I audit_event dapat dipanggil", _ok, _variants)
check("I audit.jsonl ditulis", os.path.exists(db.AUDIT_PATH), db.AUDIT_PATH)
print("  ..   AUDIT_PATH =", db.AUDIT_PATH)

# J. audit selalu lewat file + cermin PG terpasang + db.py tidak impor pg
dbsrc = open(os.path.join(BACKEND, "db.py")).read()
check("J audit_event menulis AUDIT_PATH", "AUDIT_PATH" in dbsrc)
check("J >=6 pemakaian _pg_mode()", dbsrc.count("_pg_mode()") >= 6, dbsrc.count("_pg_mode()"))
check("J db.py tidak impor pg langsung", "\nimport pg" not in dbsrc)

print("RESULTS: %d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
