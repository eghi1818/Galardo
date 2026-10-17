#!/usr/bin/env python3
"""Tes offline tools/backup.py: arsip, MANIFEST sha256, retensi, restore."""
import hashlib, json, os, shutil, sys, tarfile, tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import backup

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


sand = tempfile.mkdtemp(prefix="galardo-bak-")
os.makedirs(os.path.join(sand, "data"))
os.makedirs(os.path.join(sand, "docs"))
open(os.path.join(sand, "data", "state.json"), "w").write('{"a":1}')
open(os.path.join(sand, "docs", "HASIL-1.md"), "w").write("halo")
open(os.path.join(sand, "docs", "SESSION_STATE.md"), "w").write("state")
open(os.path.join(sand, "docs", "CATATAN.md"), "w").write("diabaikan")
out = os.path.join(sand, "backups")

print("== A. cakupan file ==")
rels = backup._files(sand)
check("A data/ ikut", any(r.startswith("data/") for r in rels), rels)
check("A HASIL-* ikut", "docs/HASIL-1.md" in rels, rels)
check("A SESSION_STATE ikut", "docs/SESSION_STATE.md" in rels, rels)
check("A dokumen lain diabaikan", "docs/CATATAN.md" not in rels, rels)

print("== B. arsip + manifest ==")
r1 = backup.make(out, 10, root=sand)
check("B arsip dibuat", os.path.isfile(r1["archive"]), r1["archive"])
with tarfile.open(r1["archive"], "r:gz") as tf:
    names = tf.getnames()
check("B ada MANIFEST.json", "MANIFEST.json" in names, names)
check("B arsip memuat data/state.json", "data/state.json" in names, names)
mf = json.loads(tarfile.open(r1["archive"], "r:gz").extractfile("MANIFEST.json").read())
real = hashlib.sha256(open(os.path.join(sand, "data", "state.json"), "rb").read()).hexdigest()
check("B sha256 manifest benar", mf["files"].get("data/state.json") == real, mf["files"])
check("B count cocok", mf["count"] == len(rels), (mf["count"], len(rels)))

print("== C. retensi ==")
for _ in range(3):
    backup.make(out, 2, root=sand)
sisa = [f for f in os.listdir(out) if f.endswith(".tar.gz")]
check("C retensi menyisakan 2", len(sisa) == 2, sisa)

print("== D. restore ==")
dest = os.path.join(sand, "restore")
backup.restore(r1["archive"], dest)
got = open(os.path.join(dest, "data", "state.json")).read()
check("D isi file pulih identik", got == '{"a":1}', got)
check("D manifest tidak ditulis", not os.path.exists(os.path.join(dest, "MANIFEST.json")))
n1 = len(backup.restore(r1["archive"], dest))
check("D tanpa --force tidak menimpa", n1 == 0, n1)
n2 = len(backup.restore(r1["archive"], dest, force=True))
check("D dengan --force menimpa", n2 > 0, n2)

shutil.rmtree(sand)
print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
