#!/usr/bin/env python3
"""Cek offline berkas Docker: Dockerfile, compose, dockerignore, dukungan GALARDO_BIND."""
import os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


def read(p):
    f = os.path.join(ROOT, p)
    return open(f).read() if os.path.isfile(f) else ""


df, dc, di = read("Dockerfile"), read("docker-compose.yml"), read(".dockerignore")

print("== A. Dockerfile ==")
check("A ada Dockerfile", bool(df))
check("A base python:3.11-slim", "python:3.11-slim" in df)
check("A set GALARDO_BIND=0.0.0.0", "GALARDO_BIND=0.0.0.0" in df)
check("A EXPOSE 8090/8095/8899", all(p in df for p in ("8090", "8095", "8899")), df[:200])
check("A ada HEALTHCHECK", "HEALTHCHECK" in df)
check("A healthcheck ke /api/v1/health", "/api/v1/health" in df)
check("A CMD run_local", "backend/run_local.py" in df)

print("== B. compose ==")
check("B ada docker-compose.yml", bool(dc))
check("B ada services:", "services:" in dc)
check("B port 8090/8095/8899", all(p in dc for p in ("8090", "8095", "8899")))
check("B volume data", "./data:/app/data" in dc)
check("B GALARDO_BIND di environment", 'GALARDO_BIND: "0.0.0.0"' in dc)
check("B restart policy", "restart:" in dc)

print("== C. dockerignore ==")
check("C ada .dockerignore", bool(di))
for pat in (".git", ".out", "backups", "__pycache__"):
    check("C mengabaikan %s" % pat, pat in di, di)

print("== D. dukungan bind di kode ==")
hits = []
for dirpath, _, names in os.walk(os.path.join(ROOT, "backend")):
    for n in names:
        if n.endswith(".py"):
            t = open(os.path.join(dirpath, n)).read()
            if "GALARDO_BIND" in t:
                hits.append(n)
check("D ada modul yang menghormati GALARDO_BIND", bool(hits), hits)
check("D default tetap 127.0.0.1",
      'os.environ.get("GALARDO_BIND", "127.0.0.1")' in read("backend/run_local.py"))


print("== E. NATS ==")
check("E service nats ada", "nats:" in dc)
check("E image nats", "nats:2.10-alpine" in dc)
check("E GALARDO_NATS_URL di env", "GALARDO_NATS_URL" in dc)
check("E depends_on nats", "depends_on" in dc and "- nats" in dc)
check("E modul bus ada", bool(read("backend/bus.py")))
check("E bus fail-open (tanpa env -> skipped)",
      "nats nonaktif" in read("backend/bus.py"))

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
