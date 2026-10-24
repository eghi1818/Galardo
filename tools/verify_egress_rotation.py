#!/usr/bin/env python3
"""verify_egress_rotation - bukti Mode B: apakah IP egress BENAR berubah lewat gateway.

Butuh GALARDO_GATEWAY_URL (host:port atau user:pass@host:port). Kalau belum diset -> SKIP
(jujur: fitur belum diuji, bukan hijau palsu).
"""
import json, os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ECHO = os.environ.get('GALARDO_ECHO_URL', 'https://api.ipify.org?format=json')
N = int(os.environ.get('GALARDO_EGRESS_SAMPLES', '12'))


def load_env():
    d = dict(os.environ)
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
            d.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return d


ENV = load_env()


def gateway():
    for k in ('GALARDO_GATEWAY_URL', 'GALARDO_GATEWAY', 'GALARDO_PROXY_GATEWAY', 'GALARDO_POOL_GATEWAY'):
        if ENV.get(k):
            return k, ENV[k].strip()
    return None, None


def fetch(url, proxy, timeout=20):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
    return op.open(url, timeout=timeout).read().decode('utf-8', 'replace').strip()


def main():
    k, spec = gateway()
    if not spec:
        print('  [skip] egress rotation: gateway belum dikonfigurasi '
              '(set GALARDO_GATEWAY_URL=host:port atau user:pass@host:port di .env)')
        return 0
    px = spec if '://' in spec else 'http://' + spec
    print('  gateway dari %s = %s' % (k, re.sub(r'//[^@]*@', '//***@', px)))
    ips = []
    for _ in range(N):
        try:
            raw = fetch(ECHO, px)
            m = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', raw)
            ips.append(m.group(1) if m else raw[:40])
        except Exception as e:
            ips.append('ERR:' + type(e).__name__)
        time.sleep(0.15)
    print('  sampel (%d): %s' % (len(ips), ', '.join(ips)))
    good = [x for x in ips if not x.startswith('ERR')]
    uniq = sorted(set(good))
    print('  IP unik: %d | error: %d' % (len(uniq), len(ips) - len(good)))
    sticky = sum(1 for a, b in zip(good, good[1:]) if a == b)
    print('  berurutan sama (indikasi sticky): %d dari %d' % (sticky, max(len(good) - 1, 0)))
    for ip in uniq[:5]:
        try:
            j = json.loads(fetch('https://ipinfo.io/%s/json' % ip, px))
            print('    %s -> %s | %s' % (ip, j.get('org', '?'), j.get('country', '?')))
        except Exception:
            pass
    fails = []

    def ok(c, label, extra=''):
        if c:
            print('  [ok]   ' + label)
        else:
            print('  [GAGAL] ' + label + ((' -> ' + str(extra)) if extra else ''))
            fails.append(label)

    ok(len(good) > 0, 'ada sampel sukses lewat gateway')
    ok(len(uniq) >= 2, 'IP egress BENAR berubah (unik >= 2)', uniq)
    if len(uniq) == 1:
        print('  catatan: cuma 1 IP -> "ribuan IP" masih KLAIM, bukan fakta')
    if fails:
        print('  [GAGAL] verify_egress_rotation: %d gagal' % len(fails))
        return 1
    print('  [ok]   verify_egress_rotation: rotasi egress terbukti (%d IP unik / %d sampel)' % (len(uniq), len(ips)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
