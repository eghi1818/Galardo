#!/usr/bin/env python3
"""Perbaiki patch STEP-126: param headers di _json, dan path di _dispatch (hanya terima method)."""
import os, re

API = 'backend/api.py'
src = open(API, encoding='utf-8').read()
orig = src

TOKENS = ['# GALARDO_LOGIN_RATE hook', '# GALARDO_COOKIE_SECURE hook', '# GALARDO_LOGIN_RATE gate',
          '# GALARDO_LOGIN_RATE handler', '_gal_login_rate_record(_gal_ip(self),',
          '_gal_login_rate_check(_gal_ip(self))', '_gal_cookie_secure(self)', '_ok_rl', '_ra_rl',
          'obj = dict(obj)', "obj['Set-Cookie'] = str(obj["]

def is_generated(line):
    if any(t in line for t in TOKENS):
        return True
    if "endswith('/login')" in line and ('self.path.split' in line or 'str(method).split' in line):
        return True
    return False

lines = src.splitlines(True)
kept = [l for l in lines if not is_generated(l)]
print('  - baris hasil patch lama dibuang: %d' % (len(lines) - len(kept)))
src = ''.join(kept)

def find_method(name):
    return re.search(r'^([ \t]*)def[ \t]+' + re.escape(name) + r'[ \t]*\(([^)]*)\)', src, re.M)

def params_of(m):
    return [p.strip().split('=')[0].strip() for p in m.group(2).split(',') if p.strip()]

def insert_after_defline(m, code):
    global src
    nl = src.index('\n', m.end())
    src = src[:nl + 1] + code + src[nl + 1:]

J = 'self._json' if 'def _json(self' in src else '_json'

# --- hook _json: pakai nama parameter yang BENAR ---
m = find_method('_json')
if not m:
    raise SystemExit('  ! _json tidak ditemukan')
pr = params_of(m)
codep = 'code' if 'code' in pr else pr[1]
hpar = 'headers' if 'headers' in pr else (pr[3] if len(pr) > 3 else 'headers')
ind = m.group(1) + '    '
code = (
    ind + "if getattr(self, 'command', '') == 'POST' and self.path.split('?')[0].rstrip('/').endswith('/login') and " + codep + " != 429:\n"
    + ind + "    _gal_login_rate_record(_gal_ip(self), " + codep + " >= 400)  # GALARDO_LOGIN_RATE hook\n"
    + ind + "if isinstance(" + hpar + ", dict) and 'Set-Cookie' in " + hpar + " and 'galardo_session=' in str(" + hpar + ".get('Set-Cookie')) and _gal_cookie_secure(self):\n"
    + ind + "    " + hpar + " = dict(" + hpar + ")\n"
    + ind + "    " + hpar + "['Set-Cookie'] = str(" + hpar + "['Set-Cookie']) + '; Secure'  # GALARDO_COOKIE_SECURE hook\n"
)
insert_after_defline(m, code)
print('  + _json hook: code=%s headers=%s (signature: %s)' % (codep, hpar, pr))

# --- gerbang _dispatch: path diambil dari self.path bila tak ada param path ---
m = find_method('_dispatch')
if not m:
    raise SystemExit('  ! _dispatch tidak ditemukan')
pr = [p for p in params_of(m) if p != 'self']
p_meth = next((p for p in pr if 'method' in p.lower() or 'verb' in p.lower()), None)
p_path = next((p for p in pr if any(k in p.lower() for k in ('path', 'route', 'uri', 'url', 'target'))), None)
path_expr = ('str(' + p_path + ')') if p_path else 'self.path'
meth_expr = ('str(' + p_meth + ").upper() == 'POST'") if p_meth else "getattr(self, 'command', '') == 'POST'"
ind = m.group(1) + '    '
code = (
    ind + "# GALARDO_LOGIN_RATE gate\n"
    + ind + "if " + meth_expr + " and " + path_expr + ".split('?')[0].rstrip('/').endswith('/login'):\n"
    + ind + "    _ok_rl, _ra_rl = _gal_login_rate_check(_gal_ip(self))\n"
    + ind + "    if not _ok_rl:\n"
    + ind + "        return " + J + "(429, {'error': 'rate_limited', 'retry_after': _ra_rl}, headers={'Retry-After': str(_ra_rl)})\n"
)
insert_after_defline(m, code)
print('  + _dispatch gate: params=%s method=%s path=%s' % (pr, p_meth, path_expr))

# --- gerbang cadangan di setiap handler bernama *login* ---
names = []
for mm in re.finditer(r'^([ \t]*)def[ \t]+(\w*login\w*)[ \t]*\(([^)]*)\)', src, re.M):
    if 'self' in [x.strip().split('=')[0].strip() for x in mm.group(3).split(',')]:
        names.append(mm.group(2))
for nm in names:
    mm = find_method(nm)
    if not mm:
        continue
    ind = mm.group(1) + '    '
    code = (
        ind + "# GALARDO_LOGIN_RATE handler\n"
        + ind + "if getattr(self, 'command', '') == 'POST' and self.path.split('?')[0].rstrip('/').endswith('/login'):\n"
        + ind + "    _ok_rl2, _ra_rl2 = _gal_login_rate_check(_gal_ip(self))\n"
        + ind + "    if not _ok_rl2:\n"
        + ind + "        return " + J + "(429, {'error': 'rate_limited', 'retry_after': _ra_rl2}, headers={'Retry-After': str(_ra_rl2)})\n"
    )
    insert_after_defline(mm, code)
    print('  + gerbang cadangan di handler: ' + nm)

if src != orig:
    open(API, 'w', encoding='utf-8').write(src)
    print('  API.PY DITULIS ULANG')
