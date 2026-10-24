#!/usr/bin/env python3
"""Pengunci pondasi Mode B: parsing spec gateway, masking, sticky, pendaftaran pool."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'backend'))

FAILS, NOK = [], 0
ENVK = ('GALARDO_GATEWAY_URL', 'GALARDO_GATEWAY_STICKY', 'GALARDO_GATEWAY_POOL')


def ok(cond, label, extra=''):
    global NOK
    if cond:
        NOK += 1
        print('  [ok]   ' + label)
    else:
        print('  [GAGAL] ' + label + ((' -> ' + str(extra)) if extra != '' else ''))
        FAILS.append(label)
    return bool(cond)


import gateway  # noqa: E402

SIMPAN = {k: os.environ.get(k) for k in ENVK}


def bersih():
    for k in ENVK:
        os.environ.pop(k, None)


try:
    ok(True, 'modul backend/gateway.py bisa diimpor')

    # --- parsing ---
    p = gateway.parse('gateway.anyip.io:8080')
    ok(p['host'] == 'gateway.anyip.io' and p['port'] == 8080 and p['scheme'] == 'http',
       'parse host:port')
    p = gateway.parse('user:rahasia@gateway.anyip.io:8080')
    ok(p['user'] == 'user' and p['password'] == 'rahasia', 'parse user:pass@host:port')
    p = gateway.parse('http://gateway.anyip.io:8080')
    ok(p['scheme'] == 'http' and p['port'] == 8080, 'parse scheme://host:port')
    p = gateway.parse('https://u:p@h.example:3128')
    ok(p['scheme'] == 'https' and p['user'] == 'u' and p['password'] == 'p', 'parse scheme://user:pass@host:port')
    p = gateway.parse('socks5h://h.example:1080')
    ok(p['scheme'] == 'socks5h', 'parse socks5h')

    # --- penolakan spec tidak sah ---
    for spec, label in (('gateway.anyip.io', 'tolak tanpa port'),
                        ('h.example:abc', 'tolak port bukan angka'),
                        ('h.example:99999', 'tolak port di luar rentang'),
                        ('ftp://h.example:21', 'tolak scheme tak didukung'),
                        ('', 'tolak spec kosong')):
        try:
            gateway.parse(spec)
            ok(False, label, 'tidak melempar')
        except gateway.GatewayError:
            ok(True, label)
        except Exception as e:
            ok(False, label, type(e).__name__)

    # --- masked ---
    bersih()
    os.environ['GALARDO_GATEWAY_URL'] = 'user:rahasia@h.example:8080'
    m = gateway.masked()
    ok('rahasia' not in m and 'user' in m and 'h.example:8080' in m, 'masked menyembunyikan sandi', m)

    # --- sticky ---
    bersih()
    os.environ['GALARDO_GATEWAY_URL'] = 'h.example:8080'
    ok(gateway.sticky() == 'worker', 'sticky default worker (bukan per request)')
    os.environ['GALARDO_GATEWAY_STICKY'] = 'request'
    ok(gateway.sticky() == 'request', 'sticky dari env dihormati')
    os.environ['GALARDO_GATEWAY_STICKY'] = 'ngawur'
    ok(gateway.sticky() == 'worker', 'sticky ngawur -> worker')

    # --- enabled / disabled ---
    bersih()
    ok(gateway.enabled() is False, 'enabled False saat env kosong (tidak error)')
    os.environ['GALARDO_GATEWAY_URL'] = 'h.example:8080'
    ok(gateway.enabled() is True, 'enabled True saat env diisi')
    os.environ['GALARDO_GATEWAY_URL'] = 'h.example'          # rusak
    ok(gateway.enabled() is False, 'enabled False saat spec rusak')

    # --- describe ---
    bersih()
    d = gateway.describe()
    ok(d['enabled'] is False and d['error'] is None, 'describe() saat kosong: enabled False')
    os.environ['GALARDO_GATEWAY_URL'] = 'u:p@h.example:8080'
    d = gateway.describe()
    ok(d['enabled'] and d['has_credentials'] and d['sticky'] == 'worker' and d['error'] is None,
       'describe() saat aktif: bentuk benar')
    os.environ['GALARDO_GATEWAY_URL'] = 'h.example'
    d = gateway.describe()
    ok(d['enabled'] is False and d['error'], 'describe() saat rusak: error terisi')

    # --- proxy_url ---
    bersih()
    os.environ['GALARDO_GATEWAY_URL'] = 'h.example:8080'
    ok(gateway.proxy_url() == 'http://h.example:8080', 'proxy_url tanpa kredensial', gateway.proxy_url())
    os.environ['GALARDO_GATEWAY_URL'] = 'https://u:p@h.example:8080'
    ok(gateway.proxy_url() == 'https://u:p@h.example:8080', 'proxy_url dengan kredensial', gateway.proxy_url())

    # --- pendaftaran ke proxypool ---
    try:
        import proxypool
        pp_nama = None
        for nm in ('register', 'add', 'put', 'set'):
            if callable(getattr(proxypool, nm, None)):
                pp_nama = nm
                break
        if pp_nama:
            os.environ['GALARDO_GATEWAY_URL'] = 'h.example:8080'
            os.environ['GALARDO_GATEWAY_POOL'] = 'gateway-uji'
            try:
                proxypool.clear()
            except Exception:
                pass
            nama = gateway.register()
            ok(nama == 'gateway-uji', 'register() memakai nama pool dari env', nama)
            got = None
            try:
                got = proxypool.resolve('gateway-uji')
            except Exception as e:
                got = 'ERR:' + type(e).__name__
            ok(got == ('h.example', 8080), 'pool terdaftar dan bisa diresolusi', got)
        else:
            print('  [ok]   proxypool tidak punya register() -> dilewati')
    except Exception as e:
        ok(False, 'pendaftaran ke proxypool', '%s: %s' % (type(e).__name__, e))

    # --- wiring di api.py (dikunci supaya tidak hilang diam-diam) ---
    _apisrc = open(os.path.join(ROOT, 'backend', 'api.py'), encoding='utf-8').read()
    ok('/gateway/status' in _apisrc, 'api.py memuat route /gateway/status')
    ok('import gateway' in _apisrc, 'api.py mengimpor gateway')
    ok('GALARDO_GATEWAY_BOOT' in _apisrc, 'api.py mendaftarkan gateway saat start')

finally:
    bersih()
    for k, v in SIMPAN.items():
        if v is not None:
            os.environ[k] = v

if FAILS:
    print('  [GAGAL] verify_gateway: %d gagal / %d cek' % (len(FAILS), NOK + len(FAILS)))
    sys.exit(1)
print('  [ok]   verify_gateway: %d cek hijau' % NOK)
