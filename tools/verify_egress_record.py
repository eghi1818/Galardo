#!/usr/bin/env python3
"""Pengunci pencatat IP egress: hitung unik, tahan worker kosong, thread-safe, reset."""
import os, sys, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
FAILS, NOK = [], 0
ENVK = ('GALARDO_GATEWAY_URL', 'GALARDO_GATEWAY_STICKY')
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


import egress  # noqa: E402

try:
    for k in ENVK:
        os.environ.pop(k, None)
    egress.reset()
    ok(True, 'modul backend/egress.py bisa diimpor')

    ok(egress.proxies() is None, 'proxies() None saat gateway mati')
    ok(egress.note() is None, 'note() None saat gateway mati (tanpa jaringan)')

    os.environ['GALARDO_GATEWAY_URL'] = 'user:rahasia@127.0.0.1:9999'
    p = egress.proxies()
    ok(p == {'http': 'http://user:rahasia@127.0.0.1:9999',
             'https': 'http://user:rahasia@127.0.0.1:9999'},
       'proxies() mengembalikan dict http+https', p)

    egress.reset()
    egress.record('w1', '10.0.0.1')
    egress.record('w2', '10.0.0.2')
    egress.record('w2', '10.0.0.2')
    s = egress.snapshot()
    ok(s['worker_tercatat'] == 2, 'hitung worker unik', s['worker_tercatat'])
    ok(s['ip_unik'] == 2, 'hitung IP unik (dedupe)', s['ip_unik'])
    ok(s['terakhir']['w2']['ip'] == '10.0.0.2', 'IP terakhir per worker tersimpan')
    ok(s['ip_unik_daftar'] == ['10.0.0.1', '10.0.0.2'], 'daftar IP unik terurut')

    egress.record('', '10.0.0.3')
    egress.record('w3', '')
    ok(egress.snapshot()['worker_tercatat'] == 2, 'worker/ip kosong diabaikan')

    egress.record(123, '10.0.0.4')
    ok('123' in egress.snapshot()['terakhir'], 'worker non-string dikoersi ke str')

    egress.reset()
    ok(egress.snapshot()['worker_tercatat'] == 0 and egress.snapshot()['ip_unik'] == 0, 'reset membersihkan')

    def kerja(i):
        for j in range(20):
            egress.record('t%d' % i, '10.1.%d.%d' % (i, j))

    th = [threading.Thread(target=kerja, args=(i,)) for i in range(5)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    s = egress.snapshot()
    ok(s['worker_tercatat'] == 5 and s['ip_unik'] == 100, 'thread-safe: 5 worker x 20 IP unik', s['ip_unik'])

finally:
    egress.reset()
    for k in ENVK:
        os.environ.pop(k, None)
    for k, v in SIMPAN.items():
        if v is not None:
            os.environ[k] = v

if FAILS:
    print('  [GAGAL] verify_egress_record: %d gagal / %d cek' % (len(FAILS), NOK + len(FAILS)))
    sys.exit(1)
print('  [ok]   verify_egress_record: %d cek hijau' % NOK)
