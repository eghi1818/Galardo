#!/usr/bin/env python3
"""P5: koherensi multi-proses db.py (dua proses nyata) + jalur mode PG.

- A: proses pembaca memuat state lebih dulu, proses lain menulis, pembaca wajib melihatnya
- B: mode PG -> perubahan cermin memicu hydrate ulang dari PG (tanpa PG hidup)
- C: sentinel inf dibuang, _save() menyetel mtime cermin
Stdlib only. Exit 1 bila ada yang gagal.
"""
import json, os, subprocess, sys, tempfile, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
import db  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


CHILD = r'''
import json, os, sys
sys.path.insert(0, %(backend)r)
import db
db.DATA_DIR = %(tmp)r
db.DB_PATH = os.path.join(%(tmp)r, "db.json")
db.AUDIT_PATH = os.path.join(%(tmp)r, "audit.jsonl")
db._state = None
db._state_mtime = 0.0
if sys.argv[1] == "read":
    db.list("users")
    sys.stdout.write("READY\n"); sys.stdout.flush()
    sys.stdin.readline()
    sys.stdout.write("RESULT " + json.dumps(db.get("users", "uji-mp")) + "\n")
    sys.stdout.flush()
else:
    db.insert("users", {"id": "uji-mp", "nama": "budi"})
    sys.stdout.write("WROTE\n"); sys.stdout.flush()
'''

tmp = tempfile.mkdtemp(prefix="galardo-p5-")
env = dict(os.environ)
env["PYTHONUNBUFFERED"] = "1"
code = CHILD % {"backend": BACKEND, "tmp": tmp}

print("== A. dua proses nyata (mode JSON) ==")
rd = subprocess.Popen([sys.executable, "-c", code, "read"], stdin=subprocess.PIPE,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
first = (rd.stdout.readline() or "").strip()
check("A pembaca siap & state termuat", first == "READY",
      first or (rd.stderr.read() or "")[-200:])
wr = subprocess.run([sys.executable, "-c", code, "write"], capture_output=True,
                    text=True, env=env)
check("A penulis sukses", wr.returncode == 0, (wr.stderr or "")[-200:])
time.sleep(0.20)
line = ""
try:
    rd.stdin.write("\n"); rd.stdin.flush()
    line = (rd.stdout.readline() or "").strip()
    rd.wait(timeout=15)
except Exception as exc:                                    # pragma: no cover
    check("A pembaca membalas", False, exc)
check("A proses lain melihat tulisan", '"uji-mp"' in line and '"budi"' in line, line)

print("== B. mode PG memicu hydrate ulang ==")
db.DATA_DIR = tmp
db.DB_PATH = os.path.join(tmp, "pg.json")
db._state = {"users": {"lama": {"id": "lama"}}}
db._state_mtime = 0.0
with open(db.DB_PATH, "w", encoding="utf-8") as fh:
    json.dump({"users": {"baru": {"id": "baru"}}}, fh)
os.utime(db.DB_PATH, (time.time() + 5, time.time() + 5))
_panggil = []
_asal_pg = db._pg_mode
_asal_hyd = db.db_pg.hydrate
try:
    db._pg_mode = lambda: True
    db.db_pg.hydrate = lambda: (_panggil.append(1),
                                {"users": {"dari-pg": {"id": "dari-pg"}}})[1]
    st = db._load()
finally:
    db._pg_mode = _asal_pg
    db.db_pg.hydrate = _asal_hyd
check("B hydrate dipanggil", len(_panggil) == 1, len(_panggil))
check("B state diambil dari PG", "dari-pg" in (st or {}).get("users", {}),
      list((st or {}).get("users", {})))

print("== C. sentinel inf dibuang ==")
check("C _mirror_mtime ada & callable", callable(getattr(db, "_mirror_mtime", None)))
db._state = {"users": {}}
db._state_mtime = float("inf")
db._save()
check("C _save tidak menyisakan inf", db._state_mtime != float("inf"), db._state_mtime)
check("C _save menyetel mtime cermin", db._state_mtime == db._mirror_mtime(),
      db._state_mtime)

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
