#!/usr/bin/env python3
"""Pengunci penemuan origin: parsing CT, pola host, klasifikasi, dedupe, ketahanan error."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
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


import origins  # noqa: E402

try:
    ok(True, 'modul backend/origins.py bisa diimpor')

    # --- pola edge ---
    for h in ('e1234.a.akamaiedge.net', 'x.edgekey.net', 'y.cloudflare.net',
              'z.fastly.net', 'q.cloudfront.net'):
        ok(origins.is_edge_host(h), 'kenali host edge: %s' % h)
    ok(not origins.is_edge_host('api.tokopedia.com'), 'host biasa bukan edge')

    # --- pola origin ---
    for h in ('origin.example.com', 'direct.example.com', 'backend.example.com', 'real.example.com'):
        ok(origins.is_origin_hint(h), 'kenali petunjuk origin: %s' % h)
    ok(not origins.is_origin_hint('www.example.com'), 'www bukan petunjuk origin')

    # --- parse CT ---
    fixture = [
        {'name_value': 'example.com\nwww.example.com'},
        {'name_value': '*.example.com'},
        {'common_name': 'api.example.com'},
        {'name_value': 'EXAMPLE.COM'},
        {'name_value': 'lain.example.net'},
        {'name_value': 'e1.a.akamaiedge.net'},
        {'name_value': 'jelek..'},
        {'bukan': 'dict-lengkap'},
    ]
    got = origins.parse_crt(fixture, domain='example.com')
    ok(got == {'example.com', 'www.example.com', 'api.example.com'}, 'parse: dedupe + wildcard + filter domain', sorted(got))
    ok('lain.example.net' not in got, 'parse: domain lain dibuang')
    ok('e1.a.akamaiedge.net' not in got, 'parse: host CDN luar domain dibuang')

    ok(origins.parse_crt({'data': [{'name_value': 'a.example.com'}]}, domain='example.com') == {'a.example.com'},
       'parse: bentuk dict {data: [...]}')
    ok(origins.parse_crt('[{"name_value":"b.example.com"}]', domain='example.com') == {'b.example.com'},
       'parse: bentuk string JSON')
    ok(origins.parse_crt(b'[{"name_value":"c.example.com"}]', domain='example.com') == {'c.example.com'},
       'parse: bentuk bytes')
    ok(origins.parse_crt(fixture) == {'example.com', 'www.example.com', 'api.example.com',
                                     'lain.example.net', 'e1.a.akamaiedge.net', 'jelek'},
       'parse: tanpa filter domain = semua host sah (jelek.. -> jelek)')

    try:
        origins.parse_crt('{bukan json', domain='x.com')
        ok(False, 'parse: JSON rusak melempar OriginError')
    except origins.OriginError:
        ok(True, 'parse: JSON rusak melempar OriginError')

    # --- klasifikasi ---
    ok(origins.classify('origin.example.com') == 'origin-hint', 'klasifikasi origin-hint')
    ok(origins.classify('e1.a.akamaiedge.net') == 'edge', 'klasifikasi edge')
    ok(origins.classify('api.example.com') == 'kandidat', 'klasifikasi kandidat')
    ok(origins.classify('api.example.com', '104.16.1.1') == 'edge-maybe', 'klasifikasi edge-maybe dari prefix CDN')
    ok(origins.classify('origin.example.com', '104.16.1.1') == 'origin-hint',
       'petunjuk nama menang atas prefix IP')

    # --- ketahanan ---
    ok(origins.resolve('host-yang-pasti-tidak-ada-xyz.invalid') == [], 'resolve host tak ada -> [] tanpa melempar')

    # --- live (opsional) ---
    try:
        c = origins.candidates('koler.space', timeout=20, resolve_hosts=False, limit=50)
        ok(c['domain'] == 'koler.space' and c['jumlah'] >= 1, 'candidates() live: domain + jumlah')
        ok(set(c['ringkas']) == {'origin-hint', 'kandidat', 'edge-maybe', 'edge'}, 'ringkas punya 4 kelas')
        ok(all(r['kelas'] for r in c['hosts']), 'tiap baris punya kelas')
    except Exception as e:
        print('  [skip] candidates() live: %s: %s' % (type(e).__name__, e))

finally:
    pass

if FAILS:
    print('  [GAGAL] verify_origins: %d gagal / %d cek' % (len(FAILS), NOK + len(FAILS)))
    sys.exit(1)
print('  [ok]   verify_origins: %d cek hijau' % NOK)
