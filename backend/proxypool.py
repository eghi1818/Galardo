"""GALARDO - resolusi nama pool proxy (HANYA untuk jalur probe).

Nama pool dipakai di skenario sebagai ``proxy_pool: "residential"``.
Resolver ini mengubah nama itu menjadi endpoint (host, port) yang bisa
dipakai transport.

Tanpa kredensial, :func:`resolve` mengembalikan ``None`` dan jalur probe
jatuh ke koneksi langsung - jadi integrasi bisa dibangun sekarang dan
diisi kapan pun pihak ketiga dilanggani.

Urutan sumber resolusi:
  1. registry in-memory (:func:`register`) - untuk uji dan pemakaian program
  2. variabel lingkungan ``GALARDO_PROXY_<NAMA>`` - mis. "host:port",
     "user:pass@host:port", atau "scheme://user:pass@host:port"

Python 3.9, stdlib saja.
"""
import os

PREFIX = "GALARDO_PROXY_"
_REGISTRY = {}


class PoolError(ValueError):
    """Spesifikasi proxy tidak sah."""


def parse_spec(spec):
    """'[scheme://][user:pass@]host:port' -> (host, port, user, password)."""
    if not isinstance(spec, str) or not spec.strip():
        raise PoolError("spesifikasi proxy kosong")
    s = spec.strip()
    if "://" in s:
        s = s.split("://", 1)[1]
    user = password = None
    if "@" in s:
        cred, s = s.rsplit("@", 1)
        if ":" in cred:
            user, password = cred.split(":", 1)
        else:
            user = cred
    if ":" not in s:
        raise PoolError("port tidak ada pada %r" % spec)
    host, port = s.rsplit(":", 1)
    if not host:
        raise PoolError("host kosong pada %r" % spec)
    try:
        port = int(port)
    except ValueError:
        raise PoolError("port bukan angka pada %r" % spec)
    if not (0 < port < 65536):
        raise PoolError("port di luar rentang pada %r" % spec)
    return host, port, user, password


def env_key(name):
    return PREFIX + name.upper().replace("-", "_")


def register(name, spec):
    """Daftarkan pool in-memory. Mengembalikan (host, port, user, password)."""
    if not name:
        raise PoolError("nama pool kosong")
    entry = parse_spec(spec)
    _REGISTRY[name] = entry
    return entry


def unregister(name):
    return _REGISTRY.pop(name, None)


def clear():
    _REGISTRY.clear()


def known():
    return sorted(_REGISTRY)


def resolve(name):
    """Kembalikan (host, port) atau None kalau pool belum diisi."""
    if not name:
        return None
    entry = _REGISTRY.get(name)
    if entry is None:
        spec = os.environ.get(env_key(name))
        if not spec:
            return None
        entry = parse_spec(spec)
    return (entry[0], entry[1])


def credentials(name):
    """Kembalikan (user, password) atau (None, None)."""
    entry = _REGISTRY.get(name)
    if entry is None:
        spec = os.environ.get(env_key(name))
        if not spec:
            return (None, None)
        entry = parse_spec(spec)
    return (entry[2], entry[3])


def apply(transport, name):
    """Pasang proxy pada transport. Kembalikan endpoint atau None.

    Toleran terhadap bentuk API transport: coba ``set_proxy(tuple)``,
    lalu ``set_proxy(host, port)``, lalu set atribut ``proxy``.
    """
    endpoint = resolve(name)
    if endpoint is None:
        return None
    setter = getattr(transport, "set_proxy", None)
    if callable(setter):
        try:
            setter(endpoint)
        except Exception:
            try:
                setter(endpoint[0], endpoint[1])
            except Exception:
                setattr(transport, "proxy", endpoint)
    else:
        setattr(transport, "proxy", endpoint)
    return endpoint
