"""GALARDO - cache buster untuk Goal 2.

Masalah
-------
Kalau target di belakang CDN (Cloudflare / Akamai / CloudFront / Fastly), spike
bisa dilayani edge dan TIDAK PERNAH menyentuh origin. Akibatnya target tidak
kolaps walau RPS sudah ribuan -- dan vonis "tidak tumbang" jadi salah.

Solusi
------
1. Setiap request diberi nonce unik `?__gb=<nonce>` + header no-cache, sehingga
   CDN tidak punya alasan mengembalikan salinan cache.
2. Respons DIPERIKSA: apakah masih cache HIT? Kalau nonce unik tapi tetap HIT,
   berarti CDN mengabaikan query string -> itu TEMUAN, bukan asumsi.

Python 3.9, stdlib only.
"""

from __future__ import annotations

import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

__all__ = [
    "BUSTER_KEY", "NO_CACHE_HEADERS", "new_run_id", "counter_nonce",
    "random_nonce", "decorate", "strip", "is_decorated", "cache_verdict",
    "detect_cdn", "pierce_ok", "Piercer", "CACHE_HIT_VERDICTS",
]

BUSTER_KEY = "__gb"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, max-age=0",
    "Pragma": "no-cache",
}
CACHE_HIT_VERDICTS = ("HIT", "HIT_AGE", "REVALIDATED")

_CDN_MARKERS = (
    ("cloudflare", ("cf-ray", "cf-cache-status", "cf-request-id")),
    ("akamai", ("x-akamai-request-id", "x-akamai-transformed", "akamai-cache-status")),
    ("cloudfront", ("x-amz-cf-id", "x-amz-cf-pop")),
    ("fastly", ("x-fastly-request-id", "x-served-by", "x-timer")),
    ("cloudfront-or-fastly", ("x-cache",)),
)
_CDN_SERVER_HINTS = (("cloudflare", "cloudflare"), ("akamai", "akamai"),
                     ("cloudfront", "cloudfront"), ("fastly", "fastly"),
                     ("varnish", "varnish"), ("nginx", "nginx"))


def new_run_id(prefix="r"):
    return "%s%s" % (prefix, secrets.token_hex(4))


def counter_nonce(run_id, seq):
    """Nonce deterministik: bisa direproduksi dari (run_id, seq)."""
    return "%s-%08x" % (run_id, int(seq) & 0xFFFFFFFF)


def random_nonce():
    return secrets.token_hex(8)


def decorate(url, key=BUSTER_KEY, value=None):
    """Tambah/replace param buster. Kembalikan (url_baru, nilai_nonce)."""
    v = value or random_nonce()
    parts = urlsplit(url)
    q = [(k, x) for k, x in parse_qsl(parts.query, keep_blank_values=True) if k != key]
    q.append((key, v))
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(q), parts.fragment)), v


def strip(url, key=BUSTER_KEY):
    """Buang param buster. Kembalikan (url_tanpa_buster, nilai_atau_None)."""
    parts = urlsplit(url)
    kept, found = [], None
    for k, x in parse_qsl(parts.query, keep_blank_values=True):
        if k == key:
            found = x
        else:
            kept.append((k, x))
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(kept), parts.fragment)), found


def is_decorated(url, key=BUSTER_KEY):
    return any(k == key for k, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True))


def _lower(headers):
    return dict((str(k).lower(), str(v or "")) for k, v in (headers or {}).items())


def detect_cdn(headers):
    """Tebak CDN dari header. Hanya penanda, bukan bukti."""
    h = _lower(headers)
    for name, keys in _CDN_MARKERS:
        if any(k in h for k in keys):
            return name
    server = h.get("server", "").lower()
    via = h.get("via", "").lower()
    for name, hint in _CDN_SERVER_HINTS:
        if hint in server or hint in via:
            return name
    return None


def cache_verdict(headers):
    """Klasifikasi apakah respons ini datang dari cache.

    verdict: HIT | MISS | HIT_AGE | UNKNOWN
    """
    h = _lower(headers)
    cdn = detect_cdn(h)
    cf = h.get("cf-cache-status", "").upper()
    if cf:
        if cf in ("HIT", "REVALIDATED", "STALE", "UPDATING"):
            return {"verdict": "HIT", "cdn": "cloudflare", "reason": "cf-cache-status=%s" % cf}
        if cf in ("MISS", "EXPIRED", "BYPASS", "DYNAMIC"):
            return {"verdict": "MISS", "cdn": "cloudflare", "reason": "cf-cache-status=%s" % cf}
    xc = h.get("x-cache", "").upper()
    if xc:
        if "HIT" in xc:
            return {"verdict": "HIT", "cdn": cdn, "reason": "x-cache=%s" % xc}
        if "MISS" in xc:
            return {"verdict": "MISS", "cdn": cdn, "reason": "x-cache=%s" % xc}
    ak = (h.get("akamai-cache-status") or "").upper()
    if ak:
        if "HIT" in ak:
            return {"verdict": "HIT", "cdn": "akamai", "reason": "akamai-cache-status=%s" % ak}
        return {"verdict": "MISS", "cdn": "akamai", "reason": "akamai-cache-status=%s" % ak}
    if h.get("x-cache-hits") not in (None, "", "0"):
        return {"verdict": "HIT", "cdn": "fastly", "reason": "x-cache-hits=%s" % h["x-cache-hits"]}
    try:
        age = int(h.get("age") or 0)
    except ValueError:
        age = 0
    if age > 0:
        return {"verdict": "HIT_AGE", "cdn": cdn, "reason": "age=%ds" % age}
    if cdn:
        return {"verdict": "UNKNOWN", "cdn": cdn, "reason": "cdn terdeteksi, tanpa header cache"}
    return {"verdict": "UNKNOWN", "cdn": None, "reason": "tanpa penanda cache"}


def pierce_ok(headers):
    """True kalau respons BUKAN dari cache."""
    return cache_verdict(headers)["verdict"] not in CACHE_HIT_VERDICTS


class Piercer(object):
    """Pembuat nonce per-request + pencatat kalau ada yang tetap kena cache."""

    def __init__(self, run_id=None, key=BUSTER_KEY, enabled=True):
        self.run_id = run_id or new_run_id()
        self.key = key
        self.enabled = bool(enabled)
        self.started_at = time.time()
        self.sent = 0
        self.hits = 0
        self.misses = 0
        self.unknown = 0
        self.hit_samples = []

    def decorate(self, url, seq=None):
        """Kembalikan (url, nonce). Kalau disabled, url tidak diubah."""
        if not self.enabled:
            return url, None
        n = seq if seq is not None else self.sent
        self.sent += 1
        return decorate(url, self.key, counter_nonce(self.run_id, n))

    def observe(self, headers, url=None, limit_samples=20):
        """Catat verdict cache. Kembalikan dict verdict."""
        v = cache_verdict(headers)
        verdict = v["verdict"]
        if verdict == "HIT":
            self.hits += 1
            if len(self.hit_samples) < limit_samples:
                self.hit_samples.append({"url": url, "reason": v["reason"], "at": time.time()})
        elif verdict == "MISS":
            self.misses += 1
        else:
            self.unknown += 1
        return v

    def stats(self):
        total = self.hits + self.misses + self.unknown
        return {
            "run_id": self.run_id,
            "enabled": self.enabled,
            "sent": self.sent,
            "observed": total,
            "hits": self.hits,
            "misses": self.misses,
            "unknown": self.unknown,
            "hit_ratio": round(self.hits / float(total), 4) if total else 0.0,
            "elapsed": round(time.time() - self.started_at, 3),
            "hit_samples": list(self.hit_samples),
            "verdict": ("cache_diabaikan" if self.hits and not self.misses
                        else "sebagian_kena_cache" if self.hits
                        else "menembus_origin" if self.misses
                        else "tak_terukur"),
        }
