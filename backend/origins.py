"""Penemuan kandidat Origin IP (pilar 5 doktrin: memutus rantai edge->origin).

Sumber: Certificate Transparency (crt.sh) + pola nama host + resolusi DNS.
Fungsi inti MURNI (bisa diuji offline); fungsi jaringan mengembalikan hasil/error yang jelas.

Catatan jujur: klasifikasi 'edge-maybe' memakai daftar prefix CDN yang KASAR. Ini penyaring
awal, bukan kebenaran. Bukti sebenarnya = request langsung ke IP itu dengan Host header target.
"""
import json
import re
import socket
import urllib.request

CRT = 'https://crt.sh/?q=%25.%s&output=json'
UA = 'galardo-origins/1'

EDGE_PAT = (
    r'akamaiedge\.net', r'edgekey\.net', r'edgesuite\.net', r'akamai\.net', r'akamaitechnologies',
    r'cloudflare\.net', r'cloudflare\.com', r'cloudflarestream', r'fastly\.net', r'fastlylb\.net',
    r'cdn77\.', r'incapdns\.net', r'stackpathdns\.com', r'kxcdn\.com', r'azureedge\.net',
    r'cloudfront\.net', r'edgecdn\.', r'llnwd\.net', r'netdna-cdn\.com', r'simplecdn\.net',
    r'cachefly\.net', r'cdngc\.net', r'edgecastcdn\.net', r'hs-sites\.com',
)
ORIGIN_HINT = ('origin', 'direct', 'backend', 'real', 'internal', 'src', 'stg', 'prod', 'lb', 'app')
EDGE_PREFIX = ('104.16.', '104.17.', '104.18.', '104.19.', '104.2', '172.64.', '172.65.', '172.66.',
               '172.67.', '172.68.', '172.69.', '172.70.', '172.71.')


class OriginError(ValueError):
    """Masukan/sumber tidak sah."""


def _bersih(host):
    h = (host or '').strip().lower().rstrip('.')
    if h.startswith('*.'):
        h = h[2:]
    return h


def is_edge_host(host):
    h = _bersih(host)
    return any(re.search(p, h) for p in EDGE_PAT)


def is_origin_hint(host):
    h = _bersih(host)
    label = h.split('.')[0] if h else ''
    return any(k in label for k in ORIGIN_HINT)


def parse_crt(payload, domain=None):
    """JSON crt.sh (list/dict/bytes/str) -> set hostname unik (difilter ke domain bila diberi)."""
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode('utf-8', 'replace')
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception as e:
            raise OriginError('JSON crt.sh tidak sah: %s' % e)
    if isinstance(payload, dict):
        payload = payload.get('data') or payload.get('results') or []
    if not isinstance(payload, list):
        raise OriginError('bentuk payload crt.sh tidak dikenal: %s' % type(payload).__name__)
    d = _bersih(domain) if domain else None
    out = set()
    for row in payload:
        if not isinstance(row, dict):
            continue
        for key in ('name_value', 'common_name', 'name'):
            v = row.get(key)
            if not v:
                continue
            for line in str(v).splitlines():
                h = _bersih(line)
                if not h or not re.match(r'^[a-z0-9.\-]+$', h):
                    continue
                if d and not (h == d or h.endswith('.' + d)):
                    continue
                out.add(h)
    return out


def fetch_crt(domain, timeout=25):
    url = CRT % _bersih(domain)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return parse_crt(r.read(), domain=domain)


def resolve(host):
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except Exception:
        return []
    ips = []
    for _fam, _t, _p, _c, sa in infos:
        ip = sa[0]
        if ip not in ips:
            ips.append(ip)
    return ips


def classify(host, ip=None):
    if is_edge_host(host):
        return 'edge'
    if is_origin_hint(host):
        return 'origin-hint'
    if ip and ip.startswith(EDGE_PREFIX):
        return 'edge-maybe'
    return 'kandidat'


def candidates(domain, timeout=25, resolve_hosts=True, limit=250):
    """Kumpulkan kandidat host/Origin untuk domain. Hasil diurutkan dari paling menjanjikan."""
    d = _bersih(domain)
    if not d:
        raise OriginError('domain kosong')
    hosts = fetch_crt(d, timeout=timeout)
    hasil = []
    for h in sorted(hosts)[:limit]:
        row = {'host': h, 'kelas': classify(h), 'ips': []}
        if resolve_hosts:
            row['ips'] = resolve(h)
            row['kelas'] = classify(h, row['ips'][0] if row['ips'] else None)
        hasil.append(row)
    urut = {'origin-hint': 0, 'kandidat': 1, 'edge-maybe': 2, 'edge': 3}
    hasil.sort(key=lambda r: (urut.get(r['kelas'], 9), r['host']))
    return {'domain': d, 'jumlah': len(hasil), 'hosts': hasil,
            'ringkas': {k: sum(1 for r in hasil if r['kelas'] == k) for k in urut},
            'catatan': 'kelas = penyaring awal; bukti asli = request ke IP dengan Host header target'}
