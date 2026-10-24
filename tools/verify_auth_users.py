#!/usr/bin/env python3
"""verify_auth_users - kunci mesin pengguna Galardo (login, sesi, peran, /users, rate-limit, cookie Secure)."""
import http.client, json, os, random, re, signal, socket, string, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, '.out')
BASE = os.environ.get('GALARDO_BASE', '').rstrip('/')
PORT = int(os.environ.get('GALARDO_VERIFY_PORT', '18131'))
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

def req(method, path, body=None, cookie=None, headers=None, port=None, timeout=15, retries=4):
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
                time.sleep(0.5)
        finally:
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass
    raise last

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
    try:
        s, _, _ = req('GET', '/api/v1/health', port=port, timeout=3, retries=1)
        return s == 200
    except Exception:
        return False

def healthy_twice(port):
    if not health(port):
        return False
    time.sleep(0.4)
    return health(port)

def free_port(start=18131, end=18160):
    for p in range(start, end):
        s = socket.socket()
        try:
            s.bind(('127.0.0.1', p))
            s.close()
            return p
        except OSError:
            s.close()
    return start

def start_app():
    if BASE:
        return None, PORT, ''
    os.makedirs(OUTDIR, exist_ok=True)
    want = free_port()
    logpath = os.path.join(OUTDIR, 'STEP-126-verify-app.log')
    log = open(logpath, 'wb')
    env = dict(os.environ)
    for k in ('GALARDO_PORT', 'PORT', 'GALARDO_LISTEN_PORT', 'GALARDO_HTTP_PORT', 'HTTP_PORT'):
        env[k] = str(want)
    env.setdefault('GALARDO_REQUIRE_AUTH', '1')
    env.setdefault('GALARDO_AUTH_LOCALHOST_EXEMPT', '0')
    p = subprocess.Popen(['sh', '-c', 'cd backend && exec python3 -u run_local.py'],
                         cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(60):
        if healthy_twice(want):
            print('  (app pid=%s di port %d)' % (p.pid, want))
            return p, want, logpath
        if p.poll() is not None:
            break
        time.sleep(0.4)
    try:
        txt = open(logpath, errors='replace').read()
    except Exception:
        txt = ''
    cands = [want]
    for m in re.finditer(r'(?:127\.0\.0\.1|localhost|0\.0\.0\.0|::1):(\d{4,5})', txt):
        c = int(m.group(1))
        if c not in cands:
            cands.append(c)
    for c in range(8090, 8096):
        if c not in cands:
            cands.append(c)
    for c in cands:
        if healthy_twice(c):
            print('  (app pid=%s hidup di port %d; kandidat=%s)' % (p.pid, c, cands))
            return p, c, logpath
    print('  [GAGAL] app tidak sehat. kandidat=%s pid_poll=%s' % (cands, p.poll()))
    print('  --- kepala log app ---')
    print('    ' + '\n    '.join(txt.splitlines()[:25]))
    return p, None, logpath

def run_checks():
    pw = admin_pw()
    ok(bool(pw), 'sandi admin terbaca dari .env')

    s, _, _ = req('GET', '/login')
    ok(s == 200, 'GET /login -> 200', s)

    s, h, _ = req('POST', '/login', {'username': 'eghi', 'password': pw})
    ck_admin = session_of(h)
    ok(s in (200, 204, 303), 'POST /login admin -> 2xx', s)
    ok(bool(ck_admin), 'cookie galardo_session terbit saat login')

    s, _, raw = req('GET', '/users', cookie=ck_admin)
    ok(s == 200, 'admin GET /users -> 200', s)
    ok(isinstance(jbody(raw), list), 'GET /users berbentuk array')

    s, _, raw = req('GET', '/users/meta', cookie=ck_admin)
    j = jbody(raw) or {}
    ok(s == 200 and isinstance(j, dict) and 'roles' in j, 'GET /users/meta -> 200 + roles', s)

    uname = 'vfy126_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(4))
    s, _, raw = req('POST', '/users', {'username': uname, 'name': 'Verifier', 'email': uname + '@x.y',
                                       'role': 'VIEWER', 'password': 'lihat123'}, cookie=ck_admin)
    j = jbody(raw) or {}
    uid = j.get('id') or j.get('uid')
    ok(s in (200, 201) and bool(uid), 'admin POST /users (VIEWER) -> 2xx + id', s)

    s, h, _ = req('POST', '/login', {'username': uname, 'password': 'lihat123'})
    ck_v = session_of(h)
    ok(s in (200, 204, 303) and bool(ck_v), 'login user baru -> 2xx + cookie', s)

    s, _, _ = req('GET', '/overview', cookie=ck_v)
    ok(s == 200, 'VIEWER GET /overview -> 200', s)
    s, _, _ = req('POST', '/engagements', {'name': 'vfy126'}, cookie=ck_v)
    ok(s == 403, 'VIEWER POST /engagements -> 403', s)
    s, _, _ = req('GET', '/users', cookie=ck_v)
    ok(s == 403, 'VIEWER GET /users -> 403', s)

    s, _, _ = req('POST', '/users', {'username': uname + 'b', 'email': 'b@x.y', 'role': 'SUPERMAN'}, cookie=ck_admin)
    ok(s == 422, 'POST /users role ngawur -> 422', s)

    s, _, _ = req('POST', '/logout', {}, cookie=ck_v)
    ok(s in (200, 204), 'POST /logout -> 2xx', s)
    s, _, _ = req('GET', '/overview', cookie=ck_v)
    ok(s == 401, 'cookie setelah logout -> 401', s)

    s, h, _ = req('POST', '/login', {'username': 'eghi', 'password': pw}, headers={'X-Forwarded-Proto': 'https'})
    ok(any('galardo_session=' in v and 'Secure' in v for v in set_cookies(h)),
       'cookie Secure saat X-Forwarded-Proto: https')
    s, h, _ = req('POST', '/login', {'username': 'eghi', 'password': pw})
    ok(any('galardo_session=' in v and 'Secure' not in v for v in set_cookies(h)),
       'cookie tanpa Secure saat http polos')

    mx = int(os.environ.get('GALARDO_LOGIN_MAX', '10'))
    codes = []
    for _ in range(mx + 5):
        s, _, _ = req('POST', '/login', {'username': 'eghi', 'password': 'salah-pasti'})
        codes.append(s)
    ok(429 in codes, 'rate-limit login -> 429 setelah %d gagal' % mx, codes)
    ok(all(c in (401, 403, 429) for c in codes), 'rate-limit tidak merusak respons lain', codes)

    if uid:
        s, _, _ = req('DELETE', '/users/' + str(uid), cookie=ck_admin)
        ok(s in (200, 204, 404), 'admin DELETE /users/{id} -> 2xx', s)

def main():
    global PORT
    p, port, logpath = start_app()
    if port is None:
        return 1
    PORT = port
    try:
        run_checks()
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
