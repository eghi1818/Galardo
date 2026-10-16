#!/usr/bin/env python3
"""Cek konsistensi halaman dashboard + validitas sintaks JS.

- nav <-> PAGE_TITLES <-> RENDER.<nama> harus konsisten
- script inline diekstrak lalu diperiksa dengan `node --check` bila node tersedia
Stdlib only. Exit 1 bila ada yang gagal.
"""
import os, re, shutil, subprocess, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HTML = os.path.join(ROOT, "dashboard", "index.html")
NON_PAGE = {"refreshLive", "visualEditor", "yamlEditor"}
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


s = open(HTML).read()
nav = set(re.findall(r'data-p="([A-Za-z_][A-Za-z0-9_]*)"', s))

titles = set()
i = s.find("PAGE_TITLES")
if i >= 0:
    b = s.find("{", i)
    e = s.find("};", b) if b >= 0 else -1
    if b >= 0 and e > b:
        titles = set(re.findall(r'(?:^|[{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', s[b:e]))

renders_all = set(re.findall(r'(?m)^RENDER\.([A-Za-z_][A-Za-z0-9_]*)\s*=', s))
renders = renders_all - NON_PAGE

print("== inventaris ==")
print("  nav=%d titles=%d halaman=%d sub-render=%d"
      % (len(nav), len(titles), len(renders), len(renders_all - renders)))
print("  nav   :", ", ".join(sorted(nav)) or "-")
print("  render:", ", ".join(sorted(renders)) or "-")

check("ada halaman terdaftar", bool(renders))
check("tiap halaman punya PAGE_TITLES", not (renders - titles), sorted(renders - titles))
check("tiap halaman punya entri nav", not (renders - nav), sorted(renders - nav))
check("tiap entri nav punya halaman", not (nav - renders), sorted(nav - renders))
check("tiap PAGE_TITLES punya halaman", not (titles - renders), sorted(titles - renders))

m = re.search(r"<script>(.*)</script>", s, re.S)
script = m.group(1) if m else ""
check("script inline ditemukan", bool(script), len(script))
if script:
    tmp = os.path.join("/tmp", "galardo_dash_check.js")
    with open(tmp, "w") as fh:
        fh.write(script)
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        check("node --check sintaks JS", r.returncode == 0,
              (r.stderr or "").strip().splitlines()[:3])
    else:
        print("  skip node --check (node tidak ada)")

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
