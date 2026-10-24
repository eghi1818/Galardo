#!/usr/bin/env python3
"""Buktikan rantai Mode B: GALARDO_PROXY_POOL -> proxypool.resolve -> transport.set_proxy.

Semua offline. Kalau ini hijau, maka begitu GALARDO_GATEWAY_URL diisi, engine lewat gateway.
"""
import inspect, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
FAILS, NOK = [], 0
ENVK = ('GALARDO_GATEWAY_URL', 'GALARDO_GATEWAY_POOL', 'GALARDO_PROXY_POOL')
SIMPAN = {k: os.environ.get(k) for k in ENVK}


def ok(cond, label, extra=''):
    global NOK
    if cond:
        NOK += 1
        print('  [ok]   ' + label)
    else:
        print('  [GAGAL] ' + label + ((' -> ' + str(extra)) if extra != '' else ''))
        FAILS.append(label)
    return bool(cond)


import gateway, proxypool, egress  # noqa: E402


class TransportPalsu:
    def __init__(self):
        self.proxy = None
        self.dipanggil = []

    def set_proxy(self, proxy):
        self.proxy = proxy
        self.dipanggil.append(proxy)


try:
    for k in ENVK:
        os.environ.pop(k, None)

    # 1. proxy.py harus membaca nama pool dari env
    psrc = open(os.path.join(ROOT, 'backend', 'proxy.py'), encoding='utf-8').read()
    ok('GALARDO_PROXY_POOL' in psrc, 'proxy.py membaca GALARDO_PROXY_POOL dari env')
    ok('proxypool.resolve' in psrc, 'proxy.py meresolusi pool lewat proxypool.resolve')

    # 2. gateway terdaftar sebagai pool, dan resolve mengembalikan host/port gateway
    os.environ['GALARDO_GATEWAY_URL'] = 'user:rahasia@gw.contoh:8080'
    os.environ['GALARDO_GATEWAY_POOL'] = 'gateway'
    os.environ['GALARDO_PROXY_POOL'] = 'gateway'
    try:
        proxypool.clear()
    except Exception:
        pass
    nama = gateway.register()
    ok(nama == 'gateway', 'gateway.register() memakai nama pool dari env', nama)
    got = None
    try:
        got = proxypool.resolve('gateway')
    except Exception as e:
        got = 'ERR:' + type(e).__name__
    ok(got == ('gw.contoh', 8080), 'pool gateway bisa diresolusi ke host/port', got)

    # 3. fungsi proxypool yang memasang proxy ke transport benar-benar memanggil set_proxy
    kandidat = []
    for nm in sorted(dir(proxypool)):
        if nm.startswith('_'):
            continue
        f = getattr(proxypool, nm)
        if not callable(f):
            continue
        try:
            ps = list(inspect.signature(f).parameters)
        except Exception:
            continue
        if len(ps) == 1:
            kandidat.append((nm, f))
    ok(bool(kandidat), 'ada fungsi proxypool yang menerima transport', [n for n, _ in kandidat])

    dipasang = False
    for nm, f in kandidat:
        t = TransportPalsu()
        try:
            f(t)
        except Exception:
            continue
        if t.dipanggil and t.dipanggil[-1] == ('gw.contoh', 8080):
            dipasang = True
            print('  (dipakai) %s(transport) -> set_proxy%s' % (nm, t.dipanggil[-1]))
            break
    ok(dipasang, 'fungsi pasang memanggil transport.set_proxy dengan endpoint gateway')

    # 4. transport punya set_proxy dan menyimpannya
    tsrc = open(os.path.join(ROOT, 'backend', 'transport.py'), encoding='utf-8').read()
    ok('def set_proxy' in tsrc, 'transport punya set_proxy')

    # 5. egress.proxies() sejalan
    ok(egress.proxies() == {'http': 'http://user:rahasia@gw.contoh:8080',
                            'https': 'http://user:rahasia@gw.contoh:8080'},
       'egress.proxies() mengembalikan URL gateway', egress.proxies())

    # 6. tanpa gateway -> tidak ada proxy (mode lama tetap jalan)
    for k in ENVK:
        os.environ.pop(k, None)
    try:
        proxypool.clear()
    except Exception:
        pass
    ok(egress.proxies() is None, 'tanpa gateway: proxies() None (mode lama aman)')

finally:
    for k in ENVK:
        os.environ.pop(k, None)
    for k, v in SIMPAN.items():
        if v is not None:
            os.environ[k] = v

if FAILS:
    print('  [GAGAL] verify_egress_wired: %d gagal / %d cek' % (len(FAILS), NOK + len(FAILS)))
    sys.exit(1)
print('  [ok]   verify_egress_wired: %d cek hijau' % NOK)
