#!/usr/bin/env python3
"""Cek konsistensi halaman dashboard: nav <-> PAGE_TITLES <-> RENDER.<nama>."""
import os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HTML = os.path.join(ROOT, "dashboard", "index.html")
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
i = s.find("PAGE_TITLES")
titles = set()
if i >= 0:
    seg = s[i:s.find("};", i)]
    titles = set(re.findall(r'(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', seg))
renders = set(re.findall(r'(?m)^RENDER\.([A-Za-z_][A-Za-z0-9_]*)\s*=', s))

print("== inventaris ==")
print("  nav=%d titles=%d render=%d" % (len(nav), len(titles), len(renders)))
print("  nav:", ", ".join(sorted(nav)) or "-")
print("  render:", ", ".join(sorted(renders)) or "-")

check("ada halaman terdaftar", bool(renders))
check("tiap RENDER punya PAGE_TITLES", not (renders - titles), sorted(renders - titles))
check("tiap RENDER punya entri nav", not (renders - nav), sorted(renders - nav))
check("tiap entri nav punya RENDER", not (nav - renders), sorted(nav - renders))
check("tiap PAGE_TITLES punya RENDER", not (titles - renders), sorted(titles - renders))

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
