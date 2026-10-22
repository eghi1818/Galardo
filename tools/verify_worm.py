#!/usr/bin/env python3
"""Item 14: kunci worm replikasi bercabang + cascade fail-closed.

- A aritmetika pohon (expected_agents) & berkas agen
- B cascade end-to-end: lahir 14 proses, koordinator berhenti renew, semua mati,
    NOL proses yatim (dihitung lewat pgrep -f run_id, bukan lewat reap)
- C agen dengan lease hilang bunuh diri sendiri (fail-closed)
- D selama renew, agen tetap hidup melewati ttl+grace
- E pengunci sumber: env terdokumentasi, target make, reap memakai pgrep
Stdlib only. Exit 1 bila ada yang gagal.
"""
import os, shutil, subprocess, sys, tempfile, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import worm  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


def hitung(penanda):
    if shutil.which("pgrep"):
        p = subprocess.run(["pgrep", "-f", penanda], capture_output=True, text=True)
        return len([x for x in (p.stdout or "").split() if x])
    out = subprocess.run(["ps", "-Ao", "command"], capture_output=True, text=True).stdout
    return len([l for l in out.splitlines() if penanda in l])


TMP = tempfile.mkdtemp(prefix="galardo-worm-")

print("== A. aritmetika pohon ==")
for r, c, d, exp in ((2, 2, 2, 14), (1, 1, 0, 1), (1, 3, 1, 4), (2, 1, 3, 8), (3, 2, 1, 9)):
    got = worm.WormTree(roots=r, children=c, max_depth=d).expected_agents()
    check("A expected_agents roots=%d children=%d depth=%d" % (r, c, d), got == exp, got)
check("A berkas agen ada", os.path.isfile(worm.AGENT), worm.AGENT)
check("A nama lease akar", worm.WormTree(run_id="x")._root_lease(1).endswith("lease-root-1.json"))

print("== B. cascade fail-closed (end-to-end) ==")
run_id = "verifyworm-%d" % os.getpid()
t = worm.WormTree(run_id=run_id, root_dir=TMP, roots=2, children=2, max_depth=2,
                  ttl=2.0, grace=1.5, renew_interval=0.3)
t.build()
n, batas = 0, time.time() + 10.0
while time.time() < batas:
    n = hitung(run_id)
    if n >= 14:
        break
    time.sleep(0.3)
check("B semua agen lahir (14 proses)", n == 14, n)
check("B expected_agents == jumlah proses nyata", t.expected_agents() == 14, t.expected_agents())
check("B alive_all melihat keturunan (bukan hanya akar)", t.alive_all() >= 14, t.alive_all())

t.stop_renew()
t0 = time.time()
batas = time.time() + 14.0
while time.time() < batas and hitung(run_id) > 0:
    time.sleep(0.3)
sisa = hitung(run_id)
print("    cascade: %.1fs, sisa proses=%d" % (time.time() - t0, sisa))
check("B semua mati setelah lease basi (tanpa sinyal)", sisa == 0, sisa)
check("B NOL proses yatim (sebelum reap)", hitung(run_id) == 0, hitung(run_id))
t.cleanup()

print("== C. agen dengan lease hilang ==")
p = subprocess.Popen([sys.executable, worm.AGENT, "--id", "yatim", "--lease",
                      os.path.join(TMP, "tidak-ada.json"), "--ttl", "1.0", "--grace", "0.5",
                      "--depth", "0", "--max-depth", "0", "--children", "0"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    rc = p.wait(timeout=10)
    check("C lease hilang -> agen bunuh diri sendiri", rc == 0, rc)
except subprocess.TimeoutExpired:
    p.kill()
    check("C lease hilang -> agen bunuh diri sendiri", False, "masih hidup")

print("== D. selama renew, agen tetap hidup ==")
rid2 = "verifykeep-%d" % os.getpid()
t2 = worm.WormTree(run_id=rid2, root_dir=TMP, roots=1, children=0, max_depth=0,
                   ttl=1.0, grace=0.5, renew_interval=0.2)
t2.build()
time.sleep(1.0 + 0.5 + 1.5)
check("D agen hidup melewati ttl+grace selama renew", hitung(rid2) == 1, hitung(rid2))
t2.cleanup()

print("== E. pengunci sumber ==")
wsrc = open(os.path.join(ROOT, "backend", "worm.py"), encoding="utf-8").read()
asrc = open(os.path.join(ROOT, "backend", "worm_agent.py"), encoding="utf-8").read()
mk = open(os.path.join(ROOT, "Makefile"), encoding="utf-8").read()
check("E reap memakai pgrep", "pgrep" in wsrc)
check("E agen fail-closed pada lease basi", "lease BASI" in asrc and "fail-closed" in asrc)
check("E agen menularkan terminasi ke anak", "terminate()" in asrc)
check("E target make worm ada", "\nworm:" in mk)
check("E env WORM terdokumentasi di 3 dokumen",
      all("GALARDO_WORM_TTL" in open(os.path.join(ROOT, "docs", f), encoding="utf-8").read()
          for f in ("DEPLOY-VPS.md", "KONEKSI-PIHAK-KETIGA.md", "PENDING.md")))

shutil.rmtree(TMP, ignore_errors=True)
print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
