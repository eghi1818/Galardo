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

m = re.search(r"<script\b([^>]*)>(.*?)</script>", s, re.S)
script = m.group(2) if m else ""
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
print("== nonce CSP (P6) ==")
import os as _os, subprocess as _sp, sys as _sys
_ROOT = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
_s = open(_os.path.join(_ROOT, "dashboard", "index.html")).read()


def _chk(name, cond, detail=""):
    try:
        check(name, cond, detail)
    except TypeError:
        check(name, cond)


_tags = re.findall(r"<script\b([^>]*)>", _s)
_chk("tepat 1 blok <script>", len(_tags) == 1, len(_tags))
_chk("script inline ber-nonce", bool(_tags) and 'nonce="{{NONCE}}"' in _tags[0],
     (_tags[0].strip() if _tags else ""))
_sty = re.findall(r"<style\b([^>]*)>", _s)
_chk("tepat 1 blok <style>", len(_sty) == 1, len(_sty))
_chk("style inline ber-nonce", bool(_sty) and 'nonce="{{NONCE}}"' in _sty[0],
     (_sty[0].strip() if _sty else ""))
_rest = _s.replace('nonce="{{NONCE}}"', "")
_chk("tidak ada placeholder {{...}} lain", "{{" not in _rest,
     (_rest[_rest.find("{{"):][:48] if "{{" in _rest else ""))

_CODE = ("import sys; sys.path.insert(0, 'backend'); import api; "
         "print(api._csp('TESTNONCE'))")


def _run_csp(env_val):
    env = dict(_os.environ)
    if env_val is None:
        env.pop("GALARDO_CSP", None)
    else:
        env["GALARDO_CSP"] = env_val
    try:
        r = _sp.run([_sys.executable, "-c", _CODE], cwd=_ROOT, env=env,
                    capture_output=True, text=True, timeout=120)
    except _sp.TimeoutExpired:
        return 1, "", ["timeout"]
    return r.returncode, r.stdout.strip(), (r.stderr or "").strip().splitlines()[-2:]


def _check_csp(label, env_val):
    rc, out, err = _run_csp(env_val)
    if rc != 0:
        _chk("_csp %s" % label, False, err or ("rc=%d" % rc))
        return
    d = {}
    for part in out.split(";"):
        part = part.strip()
        if part:
            d[part.split()[0]] = part
    ok = (("nonce-TESTNONCE" in d.get("script-src", ""))
          and ("nonce-TESTNONCE" in d.get("style-src", ""))
          and ("unsafe-inline" not in d.get("script-src", ""))
          and ("unsafe-inline" not in d.get("style-src", ""))
          and ("unsafe-inline" in d.get("script-src-attr", ""))
          and ("unsafe-inline" in d.get("style-src-attr", "")))
    _chk("_csp %s" % label, ok, out[:220])


_rc, _o, _e = _run_csp(None)
_chk("backend/api.py dapat di-import", _rc == 0, _e or _o[:120])
_check_csp("tanpa env", None)
_check_csp("env tanpa placeholder",
           "default-src 'self'; script-src 'self'; style-src 'self'")
_check_csp("env dengan placeholder",
           "script-src 'self' {nonce}; style-src 'self' {nonce}; connect-src 'self'")

print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
