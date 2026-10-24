#!/usr/bin/env python3
"""Patch idempoten STEP-126: rate-limit login (hanya gagal) + cookie Secure saat HTTPS."""
import os, re

ROOT = os.getcwd()
API = os.path.join(ROOT, 'backend', 'api.py')
src = open(API, encoding='utf-8').read()
orig = src

M_HELP = '# === GALARDO_LOGIN_RATE (126) ==='
M_HOOK = '# GALARDO_LOGIN_RATE hook'
M_GATE = '# GALARDO_LOGIN_RATE gate'
M_HNDL = '# GALARDO_LOGIN_RATE handler'
M_SEC  = '# GALARDO_COOKIE_SECURE hook'

def find_method(name):
    return re.search(r'^([ \t]*)def[ \t]+' + re.escape(name) + r'[ \t]*\(([^)]*)\)', src, re.M)

def find_login_names():
    out = []
    for m in re.finditer(r'^([ \t]*)def[ \t]+(\w*login\w*)[ \t]*\(([^)]*)\)', src, re.M):
        if 'self' in [x.strip().split('=')[0].strip() for x in m.group(3).split(',')]:
            out.append(m.group(2))
    return out

def params_of(m):
    return [p.strip().split('=')[0].strip() for p in m.group(2).split(',') if p.strip()]

def pick(ps, keys):
    for p in ps:
        if any(k in p.lower() for k in keys):
            return p
    return None

def insert_after_defline(m, code):
    global src
    nl = src.index('\n', m.end())
    src = src[:nl + 1] + code + src[nl + 1:]

# --- 1. blok helper ---
if M_HELP not in src:
    BLOCK = """
@MARK@
import time as _time
from collections import deque as _deque

_GAL_LOGIN_FAIL = {}
_GAL_LOGIN_MAX = int(os.environ.get('GALARDO_LOGIN_MAX', '10'))
_GAL_LOGIN_WINDOW = float(os.environ.get('GALARDO_LOGIN_WINDOW', '60'))
_GAL_LOGIN_RETRY = int(os.environ.get('GALARDO_LOGIN_RETRY_AFTER', '30'))


def _gal_ip(handler):
    fwd = handler.headers.get('X-Forwarded-For', '')
    if fwd:
        return fwd.split(',')[0].strip()
    try:
        return handler.client_address[0]
    except Exception:
        return '?'


def _gal_login_rate_check(ip):
    dq = _GAL_LOGIN_FAIL.get(ip)
    if not dq:
        return True, 0
    now = _time.time()
    while dq and now - dq[0] > _GAL_LOGIN_WINDOW:
        dq.popleft()
    if len(dq) >= _GAL_LOGIN_MAX:
        return False, _GAL_LOGIN_RETRY
    return True, 0


def _gal_login_rate_record(ip, failed):
    dq = _GAL_LOGIN_FAIL.setdefault(ip, _deque())
    if failed:
        dq.append(_time.time())
    else:
        dq.clear()


def _gal_cookie_secure(handler):
    flag = os.environ.get('GALARDO_COOKIE_SECURE')
    if flag == '1':
        return True
    if flag == '0':
        return False
    return handler.headers.get('X-Forwarded-Proto', '').lower() == 'https'
@MARK@
""".replace('@MARK@', M_HELP)
    m2 = re.search(r'^if\s+__name__\s*==', src, re.M)
    if m2:
        src = src[:m2.start()] + BLOCK.lstrip('\n') + '\n' + src[m2.start():]
        print('  + helper rate-limit/cookie ditanam SEBELUM blok __main__')
    else:
        src = src.rstrip('\n') + '\n' + BLOCK
        print('  + helper rate-limit/cookie ditambahkan di akhir file')
else:
    print('  = helper sudah ada')

J = 'self._json' if 'def _json(self' in src else '_json'

# --- 2. hook di _json: rekam gagal/sukses + cookie Secure ---
m = find_method('_json')
if m and M_HOOK not in src:
    pr = params_of(m)
    codep = pr[1] if len(pr) > 1 else 'code'
    hpar  = pr[2] if len(pr) > 2 else 'headers'
    ind = m.group(1) + '    '
    code = (
        ind + "if getattr(self, 'command', '') == 'POST' and self.path.split('?')[0].rstrip('/').endswith('/login') and " + codep + " != 429:\n"
        + ind + "    _gal_login_rate_record(_gal_ip(self), " + codep + " >= 400)  " + M_HOOK + "\n"
        + ind + "if isinstance(" + hpar + ", dict) and 'Set-Cookie' in " + hpar + " and 'galardo_session=' in str(" + hpar + ".get('Set-Cookie')) and _gal_cookie_secure(self):\n"
        + ind + "    " + hpar + " = dict(" + hpar + ")\n"
        + ind + "    " + hpar + "['Set-Cookie'] = str(" + hpar + "['Set-Cookie']) + '; Secure'  " + M_SEC + "\n"
    )
    insert_after_defline(m, code)
    print('  + hook di _json (rekam login, cookie Secure); param code=%s headers=%s' % (codep, hpar))
else:
    print('  = hook _json sudah ada' if m else '  ! _json TIDAK DITEMUKAN')

# --- 3. gerbang rate-limit di _dispatch ---
m = find_method('_dispatch')
if m and M_GATE not in src:
    pr = [p for p in params_of(m) if p != 'self']
    p_path = pick(pr, ['path', 'route', 'target', 'url']) or (pr[-1] if pr else 'path')
    p_meth = pick(pr, ['method', 'verb'])
    ind = m.group(1) + '    '
    meth = ("str(" + p_meth + ").upper() == 'POST'") if p_meth else "getattr(self, 'command', '') == 'POST'"
    code = (
        ind + M_GATE + "\n"
        + ind + "if " + meth + " and str(" + p_path + ").split('?')[0].rstrip('/').endswith('/login'):\n"
        + ind + "    _ok_rl, _ra_rl = _gal_login_rate_check(_gal_ip(self))\n"
        + ind + "    if not _ok_rl:\n"
        + ind + "        return " + J + "(429, {'error': 'rate_limited', 'retry_after': _ra_rl}, headers={'Retry-After': str(_ra_rl)})\n"
    )
    insert_after_defline(m, code)
    print('  + gerbang di _dispatch; param=%s method=%s' % (pr, p_meth))
else:
    print('  = gerbang _dispatch sudah ada' if m else '  ! _dispatch TIDAK DITEMUKAN (pakai gerbang handler)')

# --- 4. gerbang cadangan di handler login ---
for nm in find_login_names():
    if M_HNDL in src:
        break
    mm = find_method(nm)
    if not mm:
        continue
    ind = mm.group(1) + '    '
    code = (
        ind + M_HNDL + "\n"
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
else:
    print('  API.PY TIDAK BERUBAH (sudah patched)')
