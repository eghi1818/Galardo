"""Mode B — gateway tunggal dengan rotasi IP di sisi penyedia (mis. anyip.io).

Env kanonik:
  GALARDO_GATEWAY_URL     host:port | user:pass@host:port | scheme://host:port
                          | scheme://user:pass@host:port
  GALARDO_GATEWAY_STICKY  'worker' (default) | 'request'
  GALARDO_GATEWAY_POOL    nama pool untuk didaftarkan (default 'gateway')

Kebijakan: rotasi PER KONEKSI/WORKER secara default (bukan per request), karena alur
bersesi (VA -> callback -> cek status) akan putus kalau IP berubah tiap request.

Modul ini tidak butuh kredensial untuk hidup: env kosong -> enabled() False, tidak error.
"""
import os
import re
import urllib.request

try:
    from . import netssl as _ns
except Exception:
    try:
        import netssl as _ns
    except Exception:
        _ns = None

ENV_URL = 'GALARDO_GATEWAY_URL'
ENV_STICKY = 'GALARDO_GATEWAY_STICKY'
ENV_POOL = 'GALARDO_GATEWAY_POOL'
ENV_ECHO = 'GALARDO_ECHO_URL'
DEFAULT_POOL = 'gateway'
SCHEMES = ('http', 'https', 'socks5', 'socks5h', 'socks4')


class GatewayError(ValueError):
    """Spec gateway tidak sah."""


def _raw():
    return (os.environ.get(ENV_URL) or '').strip()


def parse(spec):
    """Uraikan spec menjadi dict: scheme, user, password, host, port."""
    if not spec or not spec.strip():
        raise GatewayError('GALARDO_GATEWAY_URL kosong')
    s = spec.strip()
    scheme = 'http'
    m = re.match(r'^([A-Za-z][A-Za-z0-9+.\-]*)://(.*)$', s)
    if m:
        scheme = m.group(1).lower()
        s = m.group(2)
    if scheme not in SCHEMES:
        raise GatewayError('scheme tidak didukung: %s' % scheme)
    user = password = None
    if '@' in s:
        cred, s = s.rsplit('@', 1)
        if ':' in cred:
            user, password = cred.split(':', 1)
        else:
            user = cred
    if ':' not in s:
        raise GatewayError('port wajib (host:port)')
    host, port = s.rsplit(':', 1)
    host = host.strip()
    if not host:
        raise GatewayError('host kosong')
    try:
        port = int(port)
    except ValueError:
        raise GatewayError('port bukan angka: %s' % port)
    if not (0 < port < 65536):
        raise GatewayError('port di luar rentang: %d' % port)
    return {'scheme': scheme, 'user': user, 'password': password, 'host': host, 'port': port}


def _cred(p):
    if not p.get('user'):
        return ''
    return p['user'] + ((':' + p['password']) if p.get('password') else '') + '@'


def enabled():
    try:
        parse(_raw())
        return True
    except GatewayError:
        return False


def proxy_url(spec=None):
    """URL proxy lengkap (untuk urllib/requests)."""
    p = parse(spec if spec is not None else _raw())
    return '%s://%s%s:%d' % (p['scheme'], _cred(p), p['host'], p['port'])


def proxy_spec():
    """host:port (dengan kredensial bila ada) — bentuk yang dipakai proxypool."""
    p = parse(_raw())
    return '%s%s:%d' % (_cred(p), p['host'], p['port'])


def masked():
    if not _raw():
        return None
    p = parse(_raw())
    return '%s://%s%s:%d' % (p['scheme'], (p['user'] + ':***@') if p.get('user') else '', p['host'], p['port'])


def sticky():
    v = (os.environ.get(ENV_STICKY) or 'worker').strip().lower()
    return v if v in ('worker', 'request') else 'worker'


def pool_name():
    return (os.environ.get(ENV_POOL) or DEFAULT_POOL).strip() or DEFAULT_POOL


def register():
    """Daftarkan gateway ke proxypool sebagai pool pool_name(). Kembalikan nama pool."""
    import proxypool
    name = pool_name()
    spec = proxy_spec()
    fn = None
    for nm in ('register', 'add', 'put', 'set'):
        fn = getattr(proxypool, nm, None)
        if callable(fn):
            break
    if not fn:
        raise GatewayError('proxypool tidak punya fungsi register')
    try:
        fn(name, spec)
    except TypeError:
        p = parse(_raw())
        fn(name, p['host'], p['port'])
    return name


def describe():
    """Ringkasan aman (sandi disamarkan) untuk endpoint/status."""
    try:
        p = parse(_raw()) if _raw() else None
        return {'enabled': bool(p), 'masked': masked(), 'sticky': sticky(),
                'pool': pool_name(), 'scheme': p['scheme'] if p else None,
                'host': p['host'] if p else None, 'port': p['port'] if p else None,
                'has_credentials': bool(p and p.get('user')), 'error': None}
    except GatewayError as e:
        return {'enabled': False, 'masked': None, 'sticky': sticky(), 'pool': pool_name(),
                'scheme': None, 'host': None, 'port': None, 'has_credentials': False,
                'error': str(e)}


def egress_ip(timeout=15, echo=None):
    """IP egress yang terlihat target, lewat gateway."""
    url = echo or os.environ.get(ENV_ECHO) or 'https://api.ipify.org?format=json'
    px = proxy_url()
    _handlers = [urllib.request.ProxyHandler({'http': px, 'https': px})]
    if _ns:
        try:
            _handlers.append(urllib.request.HTTPSHandler(context=_ns.context()))
        except Exception:
            pass
    op = urllib.request.build_opener(*_handlers)
    raw = op.open(url, timeout=timeout).read().decode('utf-8', 'replace')
    m = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', raw)
    return m.group(1) if m else raw.strip()[:64]


def egress_sample(n=6):
    out = []
    for _ in range(int(n)):
        try:
            out.append(egress_ip())
        except Exception as e:
            out.append('ERR:' + type(e).__name__)
    return out
