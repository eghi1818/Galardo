"""Sisipkan Authorization otomatis bila GALARDO_REQUIRE_AUTH aktif.

Dimuat via PYTHONPATH=. (lihat Makefile) supaya berlaku untuk skrip, -c, dan -m.
Token dibaca dari env, atau dari .env repo bila env belum memuatnya.

Matikan: GALARDO_AUTH_SHIM=0
Lewati per-request: kirim header 'Authorization' sendiri ('' = uji 401).
"""
import os


def _baca_env_token():
    if os.environ.get("GALARDO_DEV_TOKEN"):
        return
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))):
        f = os.path.join(d, ".env")
        if os.path.isfile(f):
            try:
                for line in open(f):
                    line = line.strip()
                    if line.startswith("GALARDO_DEV_TOKEN="):
                        os.environ.setdefault("GALARDO_DEV_TOKEN", line.split("=", 1)[1].strip())
                        return
            except Exception:
                pass


def _token():
    return os.environ.get("GALARDO_DEV_TOKEN", "dev-token")


def _with_token(headers):
    h = dict(headers or {})
    if "Authorization" not in h and _token():
        h["Authorization"] = "Bearer " + _token()
    return h


if os.environ.get("GALARDO_AUTH_SHIM", "1") != "0":
    _baca_env_token()

    try:
        import urllib.request as _ur
    except Exception:
        _ur = None
    if _ur is not None:
        class _AuthRequest(_ur.Request):
            def __init__(self, url, data=None, headers=None, **kw):
                super().__init__(url, data=data, headers=_with_token(headers), **kw)
        _ur.Request = _AuthRequest

    try:
        import http.client as _hc
    except Exception:
        _hc = None
    if _hc is not None:
        _orig_request = _hc.HTTPConnection.request

        def _auth_request(self, method, url, body=None, headers=None, **kw):
            return _orig_request(self, method, url, body=body,
                                 headers=_with_token(headers), **kw)

        _hc.HTTPConnection.request = _auth_request
