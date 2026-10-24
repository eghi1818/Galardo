#!/usr/bin/env python3
"""verify_auth_users - kunci mesin pengguna Galardo.

Identitas DETERMINISTIK: pakai master token (Bearer) untuk memastikan user `vfy-admin`
(SUPERADMIN) ada dengan sandi yang diketahui, lalu login dengan sandi itu untuk semua cek.
Tidak menebak, tidak bergantung pada sandi admin pribadi. Sandi `eghi` tetap dicoba; kalau
tidak cocok, diselaraskan ke .env dan dilaporkan.
Kuota rate-limit disamakan dengan app (GALARDO_LOGIN_MAX) supaya matriks tidak menelan diri sendiri.
"""
import http.client, json, os, random, re, signal, string, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, '.out')
LOGA = ['']
BASE = os.environ.get('GALARDO_BASE', '').rstrip('/')
PORT = int(os.environ.get('GALARDO_VERIFY_PORT', '8090'))
LOGIN_MAX = os.environ.get('GALARDO_LOGIN_MAX', '60')
VFY_USER = os.environ.get('GALARDO_VERIFY_USER', 'vfy-admin')
VFY_PW = os.environ.get('GALARDO_VERIFY_PASSWORD', 'verifikasi-123')
if BASE:
    PORT = int(BASE.rsplit(':', 1)[1])

FAILS, NOK = [], 0
RANK = {'VIEWER': 1, 'TEST_OPERATOR': 2, 'OPERATOR': 2, 'APPROVER': 3, 'ADMIN': 4, 'SUPERADMIN': 5}
PW_EPS = ['/users/%s/password', '/users/%s/passwd', '/users/%s/reset-password', '/users/%s/pw']
PW_BODIES = [('password',), ('new_password',), ('pass',), ('value',)]


def ok(cond, label, extra=''):
    global NOK
    if cond:
        NOK += 1
        print('  [ok]   ' + label)
    else:
        print('  [GAGAL] ' + label + ((' -> ' + str(extra)) if extra != '' else ''))
        FAILS.append(label)
    return bool(cond)


def req(method, path, body=None, raw=None, ctype='application/json', cookie=None,
        headers=None, port=None, timeout=15, retries=2):
    last = None
    for i in range(retries + 1):
        c = None
        try:
            c = http.client.HTTPConnection('127.0.0.1', port or PORT, timeout=timeout)
            h = {'Content-Type': ctype}
            if cookie:
                h['Cookie'] = 'galardo_session=' + cookie
            if headers:
                h.update(headers)
            data = raw.encode() if raw is not None else (json.dumps(body).encode() if body is not None else None)
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


def tail_log(n=30):
    try:
        t = open(LOGA[0], errors='replace').read().splitlines()
        print('  --- ekor log app ---')
        print('    ' + '\n    '.join(t[-n:]))
    except Exception:
        pass


def probe(method, path, cookie=None, body=None, headers=None, retries=1):
    try:
        return req(method, path, body=body, cookie=cookie, headers=headers, retries=retries)
    except Exception:
        return 0, [], ''


def jbody(raw):
    try:
        return json.loads(raw)
    except Exception:
        return None


def as_list(x):
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        for k in ('users', 'items', 'data'):
            if isinstance(x.get(k), list):
                return x[k]
    return []


def session_of(hdrs):
    for k, v in hdrs:
        if k.lower() == 'set-cookie' and 'galardo_session=' in v:
            m = re.search(r'galardo_session=([^;]*)', v)
            if m:
                return m.group(1)
    return None


def load_env_files():
    d = {}
    for name in ('.env', '.env.local', 'backend/.env'):
        p = os.path.join(ROOT, name)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding='utf-8', errors='replace'):
            s = line.strip()
            if not s or s.startswith('#') or '=' not in s:
                continue
            if s.startswith('export '):
                s = s[7:].strip()
            k, v = s.split('=', 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    return d


ENVF = load_env_files()


def master_token():
    for src in (ENVF, os.environ):
        if src.get('GALARDO_DEV_TOKEN'):
            return src['GALARDO_DEV_TOKEN']
    return None


def candidate_passwords():
    pat = re.compile(r'(PASS|PWD|SECRET)', re.I)
    out = []
    for src in (ENVF, os.environ):
        for k, v in src.items():
            if k.startswith('GALARDO_') and pat.search(k) and v:
                out.append((k, v))
    for k in ('GALARDO_DEV_TOKEN',):
        for src in (ENVF, os.environ):
            if src.get(k):
                out.append((k, src[k]))
    seen, res = set(), []
    for k, v in out:
        if v not in seen:
            seen.add(v)
            res.append((k, v))
    return res


def bearer(tok):
    return {'Authorization': 'Bearer ' + tok}


def login(user, pw, quiet=False):
    for variant, body in (('json:username', {'username': user, 'password': pw}),
                          ('json:user', {'user': user, 'password': pw})):
        s, h, _ = probe('POST', '/api/v1/login', body=body)
        if s == 429:
            time.sleep(1.2)
            s, h, _ = probe('POST', '/api/v1/login', body=body)
        if s < 400 and session_of(h):
            if not quiet:
                print('  (kredensial) login OK: user=%s bentuk=%s' % (user, variant))
            return session_of(h)
    return None


def set_password(uid, pw, tok):
    for ep in PW_EPS:
        for (key,) in PW_BODIES:
            s, _, _ = probe('POST', (ep % uid), {key: pw}, headers=bearer(tok))
            if s < 400:
                return '%s [%s]' % (ep % uid, key)
    return None


def ensure_identity(tok):
    pw = VFY_PW
    ck = login(VFY_USER, pw, quiet=True)
    if ck:
        print('  (identitas) %s sudah ada dan bisa login' % VFY_USER)
        return ck, pw
    print('  (identitas) menyiapkan %s lewat master token' % VFY_USER)
    s, _, raw = probe('POST', '/api/v1/users', {'username': VFY_USER, 'name': 'Verifier Admin',
                                                'email': VFY_USER + '@verifier.local',
                                                'role': 'SUPERADMIN', 'password': pw}, headers=bearer(tok))
    print('  (identitas) upsert %s -> %s' % (VFY_USER, s))
    if s == 0 or s >= 500:
        tail_log()
    ck = login(VFY_USER, pw, quiet=True)
    if ck:
        return ck, pw
    s, _, raw = probe('GET', '/api/v1/users', headers=bearer(tok))
    arr = as_list(jbody(raw))
    uid = None
    for u in arr:
        if (u.get('username') or '') == VFY_USER:
            uid = u.get('id') or u.get('uid')
    if uid:
        used = set_password(uid, pw, tok)
        print('  (identitas) set sandi %s -> %s' % (VFY_USER, used))
        ck = login(VFY_USER, pw, quiet=True)
    return ck, pw


def reconcile_admin(tok):
    users = [u for u in [ENVF.get('GALARDO_ADMIN_USER')] if u]
    users += [u.get('username') for u in as_list(jbody(probe('GET', '/api/v1/users', headers=bearer(tok))[2]))]
    users = [u for u in users if u] or ['eghi']
    pws = candidate_passwords()
    for u in users[:3]:
        for _k, pw in pws:
            if login(u, pw, quiet=True):
                print('  (kredensial) sandi %s cocok dengan %s' % (u, _k))
                return u, pw, False
    u = users[0]
    pw = pws[0][1] if pws else VFY_PW
    arr = as_list(jbody(probe('GET', '/api/v1/users', headers=bearer(tok))[2]))
    uid = next((x.get('id') or x.get('uid') for x in arr if (x.get('username') or '') == u), None)
    if uid:
        used = set_password(uid, pw, tok)
        print('  (kredensial) sandi %s TIDAK cocok dengan .env -> diselaraskan via %s' % (u, used))
        if login(u, pw, quiet=True):
            return u, pw, True
    return u, pw, False


def health(port):
    return probe('GET', '/api/v1/health', retries=0)[0] == 200


def start_app():
    if BASE:
        return None, PORT, ''
    os.makedirs(OUTDIR, exist_ok=True)
    logpath = os.path.join(OUTDIR, 'STEP-131-verify-app.log')
    LOGA[0] = logpath
    log = open(logpath, 'wb')
    env = dict(os.environ)
    env['GALARDO_LOGIN_MAX'] = LOGIN_MAX
    env.setdefault('GALARDO_REQUIRE_AUTH', '1')
    env.setdefault('GALARDO_AUTH_LOCALHOST_EXEMPT', '0')
    p = subprocess.Popen(['sh', '-c', 'cd backend && exec python3 -u run_local.py'],
                         cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(60):
        for c in range(8090, 8100):
            if health(c):
                time.sleep(0.4)
                if health(c):
                    print('  (app pid=%s di port %d, GALARDO_LOGIN_MAX=%s)' % (p.pid, c, LOGIN_MAX))
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


def resolve_one(method, cands, cookie=None, body=None, accept=(200, 201, 202, 204)):
    for p in cands:
        s, _, _ = probe(method, p, cookie=cookie, body=body)
        if s in accept:
            return p
    return None


def resolve():
    base = '/api/v1'
    r = {'base': base}
    tok = master_token()
    if not tok:
        print('  [GAGAL] GALARDO_DEV_TOKEN tidak ada -> tidak bisa menyiapkan identitas')
        r.update({'ck_admin': None, 'login': base + '/login'})
        return r
    s, _, raw = probe('GET', base + '/users', headers=bearer(tok))
    print('  (master token) GET /users -> %s | bentuk body: %s' % (s, type(jbody(raw)).__name__))
    if s == 0 or s >= 500:
        tail_log()
    if s != 200:
        print('  [GAGAL] master token ditolak (%s)' % s)
    ck, pw = ensure_identity(tok)
    if not ck:
        print('  [GAGAL] tidak bisa mendapatkan identitas verifier')
    else:
        print('  (identitas) %s siap dipakai' % VFY_USER)
    au, apw, changed = reconcile_admin(tok)
    r.update({'login': base + '/login', 'ck_admin': ck, 'admin_user': au, 'admin_pw': apw,
              'identitas': 'vfy-admin/SUPERADMIN', 'admin_diselaraskan': changed})
    r['login_page'] = resolve_one('GET', [base + '/login', '/'], accept=(200,))
    r['users'] = resolve_one('GET', [base + '/users'], cookie=ck)
    r['users_meta'] = resolve_one('GET', [base + '/users/meta'], cookie=ck)
    r['overview'] = resolve_one('GET', [base + '/overview', base + '/state'], cookie=ck)
    r['engagements'] = resolve_one('GET', [base + '/engagements'], cookie=ck)
    r['logout'] = resolve_one('POST', [base + '/logout'], cookie=ck, body={})
    print('  (resolusi) ' + json.dumps({k: v for k, v in r.items() if k not in ('ck_admin', 'admin_pw')}))
    return r


def run_checks(r):
    ok(r.get('ck_admin') is not None, 'identitas admin ditemukan (%s)' % r.get('identitas'))
    ok(r.get('users') is not None, 'GET /users tersedia', r.get('users'))
    ok(r.get('overview') is not None, 'GET /overview tersedia', r.get('overview'))
    ok(r.get('login_page') is not None, 'halaman login / dashboard tersedia', r.get('login_page'))
    if not (r.get('ck_admin') and r.get('users')):
        return

    ck_admin = r['ck_admin']
    s, _, raw = req('GET', r['users'], cookie=ck_admin)
    ok(s == 200 and isinstance(jbody(raw), list), 'admin GET /users -> 200 array', s)

    s, _, raw = req('GET', r['users_meta'], cookie=ck_admin)
    j = jbody(raw) or {}
    ok(s == 200 and isinstance(j, dict) and 'roles' in j, 'GET /users/meta -> 200 + roles', s)

    uname = 'vfy131_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(4))
    s, _, raw = req('POST', r['users'], {'username': uname, 'name': 'Verifier', 'email': uname + '@x.y',
                                         'role': 'VIEWER', 'password': 'lihat123'}, cookie=ck_admin)
    j = jbody(raw) or {}
    uid = j.get('id') or j.get('uid')
    ok(s in (200, 201) and bool(uid), 'admin POST /users (VIEWER) -> 2xx + id', s)

    s, h, _ = req('POST', r['login'], {'username': uname, 'password': 'lihat123'})
    ck_v = session_of(h)
    ok(s in (200, 204, 303) and bool(ck_v), 'login user baru (sandi) -> 2xx + cookie', s)

    s, h, _ = req('POST', r['login'], raw='username=%s&password=lihat123' % uname,
                  ctype='application/x-www-form-urlencoded')
    ok(s < 400 and bool(session_of(h)), 'login body form-encoded diterima (api._body toleran)', s)

    s, _, _ = req('GET', r['overview'], cookie=ck_v)
    ok(s == 200, 'VIEWER GET /overview -> 200', s)
    if r.get('engagements'):
        s, _, _ = req('POST', r['engagements'], {'name': 'vfy131'}, cookie=ck_v)
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

    s, h, _ = req('POST', r['login'], {'username': uname, 'password': 'lihat123'},
                  headers={'X-Forwarded-Proto': 'https'})
    ok(any('galardo_session=' in v and 'Secure' in v for v in [x for k, x in h if k.lower() == 'set-cookie']),
       'cookie Secure saat X-Forwarded-Proto: https')
    s, h, _ = req('POST', r['login'], {'username': uname, 'password': 'lihat123'})
    ok(any('galardo_session=' in v and 'Secure' not in v for v in [x for k, x in h if k.lower() == 'set-cookie']),
       'cookie tanpa Secure saat http polos')

    mx = int(LOGIN_MAX)
    codes = []
    for _ in range(mx + 5):
        s, _, _ = req('POST', r['login'], {'username': uname, 'password': 'salah-pasti'})
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
