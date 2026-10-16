#!/usr/bin/env python3
"""Buktikan proxy_pool mengalir sampai ke dokumen skenario ternormalisasi.

Tanpa HTTP, tanpa auth, tanpa server: panggil parser skenario langsung
dengan targets_by_name yang dibangun sendiri.
"""
import inspect
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import scenario  # noqa: E402

SE = getattr(scenario, "ScenarioError", Exception)
PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS %s" % name)
    else:
        FAIL += 1
        print("FAIL %s   <-- %s" % (name, str(detail)[:200]))


tsrc = (ROOT / "tests" / "tests_integration.py").read_text(encoding="utf-8")
m = re.search(r'FIX_VALID = """(.*?)"""', tsrc, re.S)
if not m:
    m = re.search(r"FIX_VALID = '''(.*?)'''", tsrc, re.S)
check("FIX_VALID terbaca dari tes", m is not None)
base = m.group(1) if m else ""

ref = "galardo-lab-target"
tm = re.search(r'target_ref:\s*"([^"]+)"', base)
if tm:
    ref = tm.group(1)
print("   target_ref: %s" % ref)

target = {
    "id": "tgt-lab",
    "name": ref,
    "canonical_origin": "http://127.0.0.1:18779",
    "status": "VERIFIED",
    "ownership": "dns_txt",
    "allowed_paths": ["/", "/healthz", "/api/slow", "/api/error", "/api/heavy"],
    "probe_contract": {"url": "http://127.0.0.1:18779/healthz",
                       "expected_status": 200},
    "connect_ip": None,
}
targets_by_name = {ref: target, "tgt-lab": target}

fn = getattr(scenario, "parse_scenario_yaml", None)
check("parse_scenario_yaml ada", callable(fn))
if not callable(fn):
    print()
    print("HASIL: %d passed, %d failed" % (PASS, FAIL))
    sys.exit(1)
print("   tanda tangan: %s" % str(inspect.signature(fn)))


def parse(text):
    return fn(text, dict(targets_by_name))


norm = None
err = None
try:
    norm = parse(base + "proxy_pool: 'residential'\n")
except Exception as e:
    err = e
    print("   exception: %s: %s" % (type(e).__name__, str(e)[:300]))
check("skenario dengan proxy_pool bisa diparse", err is None,
      "%s: %s" % (type(err).__name__, err) if err else "")

if isinstance(norm, dict):
    check("proxy_pool bertahan di dokumen ternormalisasi",
          norm.get("proxy_pool") == ["residential"],
          "nilai=%r" % (norm.get("proxy_pool"),))
    try:
        norm_plain = parse(base)
        check("tanpa proxy_pool -> tidak ada kunci proxy_pool",
              "proxy_pool" not in norm_plain, sorted(norm_plain)[:14])
    except Exception as e:
        check("tanpa proxy_pool -> bisa diparse", False, "%s: %s" % (type(e).__name__, e))
    if isinstance(norm, dict) and "scenario_sha256" in norm:
        try:
            n2 = parse(base + "proxy_pool: ['a:1', 'b:2']\n")
            check("daftar proxy dipertahankan apa adanya",
                  n2.get("proxy_pool") == ["a:1", "b:2"], n2.get("proxy_pool"))
            check("sha berbeda antara ada dan tanpa proxy_pool",
                  n2.get("scenario_sha256") != parse(base).get("scenario_sha256"))
        except Exception as e:
            check("daftar proxy bisa diparse", False, "%s: %s" % (type(e).__name__, e))
else:
    check("hasil parse berupa dict", False, type(norm).__name__)

bad = None
try:
    parse(base + "proxy_pool: 12345\n")
except Exception as e:
    bad = e
check("bentuk salah ditolak dengan ScenarioError", isinstance(bad, SE),
      type(bad).__name__ if bad else "tidak ada exception")
print("   (pesan: %s)" % (str(bad)[:160] if bad else "-"))

bad2 = None
try:
    parse(base + "proxy_pool: ['ok', 7]\n")
except Exception as e:
    bad2 = e
check("daftar dengan elemen non-string ditolak", isinstance(bad2, SE),
      type(bad2).__name__ if bad2 else "tidak ada exception")

print()
print("HASIL: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
