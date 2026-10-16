"""GALARDO - atribusi lapisan kegagalan: DNS / edge / origin / app / sisi kita.

Masalah
-------
Vonis "DOWN" satu label itu menyesatkan. Kasus nyata: doku.com tidak bisa diakses
karena origin tidak terjangkau edge Akamai (error 102) -- itu kegagalan ORIGIN,
bukan DNS dan bukan edge. Salah lapisan = salah laporan, salah tindakan.

Modul ini mengklasifikasi BUKTI, bukan menebak. Tidak melakukan I/O sendiri;
semua observasi disuntikkan supaya bisa diuji tanpa jaringan.

Lapisan: ours | dns | edge | origin | app | healthy | unknown

Python 3.9, stdlib only.
"""

from __future__ import annotations

__all__ = ["LAYERS", "DOWN_LAYERS", "classify", "tier_hint", "summarize", "is_down"]

LAYERS = ("ours", "dns", "edge", "origin", "app", "healthy", "unknown")
DOWN_LAYERS = ("dns", "edge", "origin", "app")

_TIER_HINTS = {
    "ours": "cek egress/proxy kita dulu; jalankan probe ke target KONTROL",
    "dns": "cek resolver & record lewat netdns; rung 1 kepemilikan tak bisa dipakai",
    "edge": "uji CDN: T1 hosts / T2 shim / T3 Edge Rule; pastikan cache-buster aktif",
    "origin": "tembak direct-to-origin (connect_ip) untuk memisahkan dari CDN",
    "app": "4xx = masalah aplikasi; cek assertions dan kontrak endpoint",
    "healthy": "target sehat; naikkan beban atau periksa ambang",
    "unknown": "tambah probe: dns, tcp, tls, http",
}

_SERVER_CDN = (("cloudflare", "cloudflare"), ("akamai", "akamai"),
               ("cloudfront", "cloudfront"), ("fastly", "fastly"),
               ("varnish", "varnish"))


def _sec(obs, name):
    v = (obs or {}).get(name)
    return v if isinstance(v, dict) else None


def _ok(obs, name):
    s = _sec(obs, name)
    if s is None:
        return None
    v = s.get("ok")
    return None if v is None else bool(v)


def _mini_cdn(headers):
    h = dict((str(k).lower(), str(v or "")) for k, v in (headers or {}).items())
    if "cf-ray" in h or "cf-cache-status" in h:
        return "cloudflare"
    if "x-amz-cf-id" in h:
        return "cloudfront"
    if "x-akamai-request-id" in h or "akamai-cache-status" in h:
        return "akamai"
    if "x-served-by" in h or "x-fastly-request-id" in h:
        return "fastly"
    server = h.get("server", "").lower()
    for name, hint in _SERVER_CDN:
        if hint in server:
            return name
    return None


def _cdn(obs):
    if (obs or {}).get("cdn"):
        return str(obs["cdn"]).lower()
    h = (_sec(obs, "http") or {}).get("headers") or {}
    try:
        from cachebuster import detect_cdn   # noqa: WPS433
        got = detect_cdn(h)
        if got:
            return got
    except Exception:
        pass
    return _mini_cdn(h)


def _signals(obs):
    return sum(1 for n in ("dns", "tcp", "tls", "http") if _ok(obs, n) is not None)


def _confidence(obs, layer):
    n = _signals(obs)
    if layer == "unknown":
        return "low"
    if n >= 3:
        return "high"
    if n == 2:
        return "medium"
    return "low"


def _result(layer, obs, reason, evidence=None):
    cdn = _cdn(obs)
    return {
        "layer": layer,
        "is_down": layer in DOWN_LAYERS,
        "confidence": _confidence(obs, layer),
        "cdn": cdn,
        "reason": reason,
        "tier_hint": _TIER_HINTS[layer],
        "evidence": evidence or {},
    }


def classify(obs, control_ok=True):
    """Klasifikasi lapisan dari observasi yang disuntikkan.

    obs: {"dns": {"ok":bool,"rcode":str}, "tcp": {"ok":bool,"error":str},
          "tls": {"ok":bool,"error":str}, "http": {"ok":bool,"status":int,"error":str,
          "headers":dict}, "cdn": str}
    control_ok: hasil probe ke target KONTROL. False -> kegagalan ada di sisi kita.
    """
    obs = obs or {}

    if not control_ok:
        return _result("ours", obs,
                       "target kontrol juga gagal -> masalah di jalur kita, bukan target",
                       {"control_ok": False})

    dns_ok = _ok(obs, "dns")
    if dns_ok is False:
        s = _sec(obs, "dns") or {}
        return _result("dns", obs,
                       "DNS gagal (rcode=%s)" % s.get("rcode"),
                       {"rcode": s.get("rcode"), "addrs": s.get("addrs")})

    cdn = _cdn(obs)

    tcp_ok = _ok(obs, "tcp")
    if tcp_ok is False:
        s = _sec(obs, "tcp") or {}
        layer = "edge" if cdn else "origin"
        return _result(layer, obs,
                       "TCP gagal%s (%s)" % (" di depan CDN" if cdn else "", s.get("error")),
                       {"error": s.get("error"), "cdn": cdn})

    tls_ok = _ok(obs, "tls")
    if tls_ok is False:
        s = _sec(obs, "tls") or {}
        layer = "edge" if cdn else "origin"
        return _result(layer, obs,
                       "TLS gagal%s (%s)" % (" di depan CDN" if cdn else "", s.get("error")),
                       {"error": s.get("error"), "issuer": s.get("issuer")})

    h = _sec(obs, "http")
    if h is not None:
        status = h.get("status")
        err = (h.get("error") or "")
        if h.get("ok") is False and not isinstance(status, int):
            low = err.lower()
            is_timeout = ("timeout" in low or "timed out" in low or "reset" in low
                          or "refused" in low)
            layer = "edge" if (cdn and is_timeout) else ("origin" if is_timeout else "unknown")
            return _result(layer, obs, "HTTP gagal tanpa status (%s)" % err,
                           {"error": err, "cdn": cdn})
        if isinstance(status, int):
            if status >= 500:
                layer = "edge" if cdn else "origin"
                return _result(layer, obs,
                               "HTTP %d%s" % (status, " dari edge CDN" if cdn else ""),
                               {"status": status, "cdn": cdn})
            if status >= 400:
                return _result("app", obs, "HTTP %d (lapisan aplikasi)" % status,
                               {"status": status})
            return _result("healthy", obs, "HTTP %d" % status, {"status": status})

    if _signals(obs) == 0:
        return _result("unknown", obs, "tidak ada observasi yang bisa dipakai")
    return _result("unknown", obs, "observasi tidak cukup untuk menyimpulkan lapisan")


def tier_hint(layer):
    return _TIER_HINTS.get(layer, _TIER_HINTS["unknown"])


def is_down(layer):
    return layer in DOWN_LAYERS


def summarize(result):
    """Satu baris untuk laporan/evidence."""
    if not isinstance(result, dict):
        return "atribusi tidak tersedia"
    return "lapisan=%s down=%s keyakinan=%s cdn=%s | %s | saran: %s" % (
        result.get("layer"), result.get("is_down"), result.get("confidence"),
        result.get("cdn") or "-", result.get("reason"), result.get("tier_hint"))
