#!/usr/bin/env python3
"""verify_auth_users - kunci mesin pengguna Galardo (resolusi endpoint sendiri, base /api/v1)."""
import http.client, json, os, random, re, signal, string, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, '.out')
BASE = os.environ.get('GALARDO_BASE', '').rstrip('/')
PORT = int(os.environ.get('GALARDO_VERIFY_PORT', '8090'))
ADMIN_USER = os.environ.get('GALARDO_ADMIN_USER', 'eghi')
if BASE:
    PORT = int(BASE.rsplit(':', 1)[1])

FAILS, NOK = [], 0

def ok(cond, label, extra=''):
    global NOK
    if cond:
        NOK += 1
        print('  [ok]   ' + label)
    else:
        print('  [GAGAL] ' + label + ((' -> ' + str(extra)) if extra != '' else ''))
        FAILS.append(label)
    return bool(cond)

def req(method, path, body=None, cookie=None, headers=None, port=None, timeout=15, retries=3):
    last = None
    for i in range(retries + 1):
        c = None
        try:
            c = http.client.HTTPConnection('127.0.0.1', port or PORT, timeout=timeout)
            h = {'Content-Type': 'application/json'}
            if cookie:
                h['Cookie'] = 'galardo_session=' + cookie
            if headers:
                h.update(headers)
            data = json.dumps(body).encode() if body is not None else None
            c.request(method, path, body=data, headers=h)
            r = c.getresponse()
            return r.status, r.getheaders(), r.read().decode('utf-8', 'replace')
        except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, OSError) as e:
            last = e
            if i < retries:
                time.sleep(0.4)
        finally:
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass
    raise last

def probe(method, path, cookie=None, body=None, retries=1):
    try:
        return req(method, path, body=body, cookie=cookie, retries=retries)
    except Exception:
        return 0, [], ''

def jbody(raw):
    try:
        return json.loads(raw)
    except Exception:
        return None

def set_cookies(hdrs):
    return [v for k, v in hdrs if k.lower() == 'set-cookie']

def session_of(hdrs):
    for v in set_cookies(hdrs):
        m = re.search(r'galardo_session=([^;]*)', v)
        if m:
            return m.group(1)
    return None

def admin_pw():
    p = os.path.join(ROOT, '.env')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            if line.startswith('GALARDO_ADMIN_PASSWORD='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return os.environ.get('GALARDO_ADMIN_PASSWORD', '')

def health(port):
    return probe('GET', '/api/v1/health', retries=0)[0] == 200

def start_app():
    if BASE:
        return None, PORT, ''
    os.makedirs(OUTDIR, exist_ok=True)
    logpath = os.path.join(OUTDIR, 'STEP-128-verify-app.log')
    log = open(logpath, 'wb')
    env = dict(os.environ)
    env.setdefault('GALARDO_REQUIRE_AUTH', '1')
    env.setdefault('GALARDO_AUTH_LOCALHOST_EXEMPT', '0')
    p = subprocess.Popen(['sh', '-c', 'cd backend && exec python3 -u run_local.py'],
                         cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(60):
        for c in range(8090, 8100):
            if health(c):
                time.sleep(0.4)
                if health(c):
                    print('  (app pid=%s di port %d)' % (p.pid, c))
                    return p, c, logpath
        if p.poll() is not None:
            break
        time.sleep(0.3)
    try:
        txt = open(logpath, errors='replace').read()
    except Exception:
        txt = ''
    print('  [GAGAL] app tidak sehat (pid_poll=%s)' % p.poll())
    print('    ' + '\n    '.join(txt.splitlines()[-15:]))
    return p, None, logpath

def diag(method, cands, cookie=None, body=None):
    parts = []
    for p in cands:
        s, _, _ = probe(method, p, cookie=cookie, body=body)
        parts.append('%s %s -> %s' % (method, p, s))
    print('  (diag) ' + ' | '.join(parts))

def resolve_one(method, cands, cookie=None, body=None, need_cookie=False, accept=(200, 201, 202, 204)):
    for p in cands:
        s, h, _ = probe(method, p, cookie=cookie, body=body)
        if s in accept and (not need_cookie or session_of(h)):
            return p
    return None

def resolve():
    pw = admin_pw()
    base = None
    for b in ('/api/v1', ''):
        if probe('GET', b + '/health')[0] == 200:
            base = b
            break
    r = {'base': base if base is not None else '/api/v1'}
    base = r['base']

    s, h, _ = probe('POST', base + '/login', body={'username': ADMIN_USER, 'password': pw})
    ck = session_of(h)
    if s < 400 and ck:
        r['login'] = base + '/login'
        r['ck_admin'] = ck
    else:
        r['login'] = None
        r['ck_admin'] = None
        diag('POST', [b + '/login' for b in ('/api/v1', '', '/api/v1/auth', '/auth')],
             body={'username': ADMIN_USER, 'password': pw})
    ck = r['ck_admin']

    r['login_page'] = resolve_one('GET', [base + '/login', '/login'], accept=(200,))
    r['users'] = resolve_one('GET', [base + '/users', '/users'], cookie=ck)
    r['users_meta'] = resolve_one('GET', [base + '/users/meta', '/users/meta'], cookie=ck)
    r['overview'] = resolve_one('GET', [base + '/overview', base + '/state', base + '/summary'], cookie=ck)
    r['engagements'] = resolve_one('GET', [base + '/engagements', '/engagements'], cookie=ck)
    r['logout'] = resolve_one('POST', [base + '/logout', '/logout'], cookie=ck, body={})

    if r['users'] is None:
        diag('GET', [base + '/users', '/users'], cookie=ck)
    if r['overview'] is None:
        diag('GET', [base + '/overview', base + '/state'], cookie=ck)
    if r['engagements'] is None:
        diag('GET', [base + '/engagements'], cookie=ck)
    print('  (resolusi) ' + json.dumps({k: v for k, v in r.items() if k != 'ck_admin'}))
    return r

def run_checks(r):
    pw = admin_pw()
    ok(bool(pw), 'sandi admin terbaca dari .env')
    ok(r.get('login') is not None, 'POST /login -> 2xx + cookie galardo_session', r.get('login'))
    ok(r.get('login_page') is not None or probe('GET', '/')[0] == 200,
       'halaman login / dashboard tersedia', r.get('login_page'))
    ok(r.get('users') is not None, 'GET /users tersedia', r.get('users'))
    ok(r.get('overview') is not None, 'GET /overview tersedia', r.get('overview'))
    if r.get('login') is None or r.get('users') is None:
        return

    ck_admin = r['ck_admin']
    s, _, raw = req('GET', r['users'], cookie=ck_admin)
    ok(s == 200, 'admin GET /users -> 200', s)
    ok(isinstance(jbody(raw), list), 'GET /users berbentuk array')

    s, _, raw = req('GET', r['users_meta'], cookie=ck_admin)
    j = jbody(raw) or {}
    ok(s == 200 and isinstance(j, dict) and 'roles' in j, 'GET /users/meta -> 200 + roles', s)

    uname = 'vfy128_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(4))
    s, _, raw = req('POST', r['users'], {'username': uname, 'name': 'Verifier', 'email': uname + '@x.y',
                                         'role': 'VIEWER', 'password': 'lihat123'}, cookie=ck_admin)
    j = jbody(raw) or {}
    uid = j.get('id') or j.get('uid')
    ok(s in (200, 201) and bool(uid), 'admin POST /users (VIEWER) -> 2xx + id', s)

    s, h, _ = req('POST', r['login'], {'username': uname, 'password': 'lihat123'})
    ck_v = session_of(h)
    ok(s in (200, 204, 303) and bool(ck_v), 'login user baru -> 2xx + cookie', s)

    s, _, _ = req('GET', r['overview'], cookie=ck_v)
    ok(s == 200, 'VIEWER GET /overview -> 200', s)
    if r.get('engagements'):
        s, _, _ = req('POST', r['engagements'], {'name': 'vfy128'}, cookie=ck_v)
        ok(s == 403, 'VIEWER POST /engagements -> 403', s)
    s, _, _ = req('GET', r['users'], cookie=ck_v)
    ok(s == 403, 'VIEWER GET /users -> 403', s)

    s, _, _ = req('POST', r['users'], {'username': uname + 'b', 'email': 'b@x.y', 'role': 'SUPERMAN'}, cookie=ck_admin)
    ok(s == 422, 'POST /users role ngawur -> 422', s)

    if r.get('logout'):
        s, _, _ = req('POST', r['logout'], {}, cookie=ck_v)
        ok(s in (200, 204), 'POST /logout -> 2xx', s)
        s, _, _ = req('GET', r['overview'], cookie=ck_v)
        ok(s == 401, 'cookie setelah logout -> 401', s)

    s, h, _ = req('POST', r['login'], {'username': ADMIN_USER, 'password': pw},
                  headers={'X-Forwarded-Proto': 'https'})
    ok(any('galardo_session=' in v and 'Secure' in v for v in set_cookies(h)),
       'cookie Secure saat X-Forwarded-Proto: https')
    s, h, _ = req('POST', r['login'], {'username': ADMIN_USER, 'password': pw})
    ok(any('galardo_session=' in v and 'Secure' not in v for v in set_cookies(h)),
       'cookie tanpa Secure saat http polos')

    mx = int(os.environ.get('GALARDO_LOGIN_MAX', '10'))
    codes = []
    for _ in range(mx + 5):
        s, _, _ = req('POST', r['login'], {'username': ADMIN_USER, 'password': 'salah-pasti'})
        codes.append(s)
    ok(429 in codes, 'rate-limit login -> 429 setelah %d gagal' % mx, codes)
    ok(all(c in (401, 403, 429) for c in codes), 'rate-limit tidak merusak respons lain', codes)

    if uid:
        s, _, _ = req('DELETE', r['users'].rstrip('/') + '/' + str(uid), cookie=ck_admin)
        ok(s in (200, 204, 404), 'admin DELETE /users/{id} -> 2xx', s)

def main():
    global PORT
    p, port, logpath = start_app()
    if port is None:
        return 1
    PORT = port
    try:
        run_checks(resolve())
    except Exception:
        import traceback
        traceback.print_exc()
        FAILS.append('exception')
        try:
            txt = open(logpath, errors='replace').read()
            print('  --- ekor log app ---')
            print('    ' + '\n    '.join(txt.splitlines()[-15:]))
        except Exception:
            pass
    finally:
        if p is not None:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                p.wait(timeout=8)
            except Exception:
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                except Exception:
                    pass
    if FAILS:
        print('  [GAGAL] verify_auth_users: %d gagal / %d cek' % (len(FAILS), NOK + len(FAILS)))
        return 1
    print('  [ok]   verify_auth_users: %d cek hijau' % NOK)
    return 0

if __name__ == '__main__':
    sys.exit(main())
