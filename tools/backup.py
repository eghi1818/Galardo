#!/usr/bin/env python3
"""Backup Galardo: data/ + docs/HASIL-*.md + SESSION_STATE.md, dengan MANIFEST sha256.

Pakai: python3 tools/backup.py [--out DIR] [--keep N] [--restore FILE] [--dest DIR] [--force]
Stdlib saja.
"""
import argparse, hashlib, json, os, sys, tarfile, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _files(root):
    out = []
    for base in ("data", "docs"):
        d = os.path.join(root, base)
        if not os.path.isdir(d):
            continue
        for dirpath, _, names in os.walk(d):
            for n in names:
                if base == "docs" and not (n.startswith("HASIL-") or n == "SESSION_STATE.md"):
                    continue
                p = os.path.join(dirpath, n)
                out.append(os.path.relpath(p, root))
    return sorted(out)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make(out_dir, keep, root=ROOT):
    os.makedirs(out_dir, exist_ok=True)
    rels = _files(root)
    manifest = {"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "root": root, "count": len(rels),
                "files": {r: _sha(os.path.join(root, r)) for r in rels}}
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    arc = os.path.join(out_dir, "galardo-%s.tar.gz" % stamp)
    n = 1
    while os.path.exists(arc):
        arc = os.path.join(out_dir, "galardo-%s-%d.tar.gz" % (stamp, n))
        n += 1
    with tarfile.open(arc, "w:gz") as tf:
        for r in rels:
            tf.add(os.path.join(root, r), arcname=r)
        mf = os.path.join(out_dir, ".manifest.tmp")
        with open(mf, "w") as fh:
            json.dump(manifest, fh, indent=1)
        tf.add(mf, arcname="MANIFEST.json")
    os.remove(mf)
    pruned = []
    arcs = sorted(f for f in os.listdir(out_dir)
                  if f.startswith("galardo-") and f.endswith(".tar.gz"))
    for old in arcs[:-keep] if keep > 0 else []:
        os.remove(os.path.join(out_dir, old)); pruned.append(old)
    return {"archive": arc, "files": len(rels), "pruned": pruned}


def restore(arc, dest, force=False):
    written = []
    with tarfile.open(arc, "r:gz") as tf:
        for m in tf.getmembers():
            if m.name == "MANIFEST.json" or not m.isfile():
                continue
            target = os.path.join(dest, m.name)
            if os.path.exists(target) and not force:
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with tf.extractfile(m) as src, open(target, "wb") as fh:
                fh.write(src.read())
            written.append(m.name)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "backups"))
    ap.add_argument("--keep", type=int, default=10)
    ap.add_argument("--restore")
    ap.add_argument("--dest", default=ROOT)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.restore:
        w = restore(a.restore, a.dest, a.force)
        print("restore: %d file -> %s" % (len(w), a.dest)); return 0
    r = make(a.out, a.keep)
    print("backup : %s" % r["archive"])
    print("file   : %d" % r["files"])
    print("pruned : %s" % (", ".join(r["pruned"]) or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
