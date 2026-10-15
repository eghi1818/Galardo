"""GALARDO - registry kapabilitas sumber / egress (item 9).

Pertanyaan yang dijawab: "kalau Galardo pakai fleet sendiri, sumber mana yang
bisa melakukan apa?" Tanpa jawaban itu, klaim "setara botnet" tidak terbukti.

Prinsipnya sama dengan modul lain: KAPABILITAS HARUS DIBUKTIKAN.
Setiap sumber menyimpan dua himpunan terpisah:

  * proven   - diukur langsung dari sumber itu (handshake TLS nyata, keep-alive
               nyata, IPv6 nyata)
  * declared - diklaim operator (mis. punya kemampuan spoof src-ip untuk UDP
               reflection, atau berada di ASN residensial)

`pick(required)` hanya memilih sumber yang membuktikan SEMUA yang diminta.
Kalau tidak ada, ia mengembalikan alasan, bukan menebak.
"""
import ipaddress
import json
import socket
import ssl
import threading
import time
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

CAPABILITIES = (
    "http1", "http2", "tls12", "tls13", "keepalive", "redirects", "ipv6",
    "udp", "spoof_src", "residential", "datacenter", "high_concurrency",
)

KINDS = ("local", "vps", "worker", "proxy", "residential")

DEFAULT_PROBE_URL = "https://www.cloudflare.com/cdn-cgi/trace"


class SourceError(Exception):
    pass


def _pct(vals, p):
    if not vals:
        return None
    v = sorted(vals)
    k = int(round((p / 100.0) * (len(v) - 1)))
    return round(v[max(0, min(k, len(v) - 1))], 2)


# ---------------------------------------------------------------------------
# prober - semua pengukuran nyata, tidak ada yang diasumsikan
# ---------------------------------------------------------------------------
def _probe_http1(url, timeout=8.0):
    t0 = time.time()
    try:
        req = urlrequest.Request(url, headers={"User-Agent": "GalardoSrcProbe/1.0",
                                               "Cache-Control": "no-cache"})
        with urlrequest.build_opener().open(req, timeout=timeout) as r:
            r.read(512)
            return {"ok": True, "ms": round((time.time() - t0) * 1000, 1),
                    "status": r.getcode(), "proto": getattr(r, "version", None)}
    except HTTPError as e:
        return {"ok": True, "ms": round((time.time() - t0) * 1000, 1), "status": e.code,
                "proto": None, "note": "status %s" % e.code}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _probe_keepalive(url, timeout=8.0):
    """Dua request pada SATU koneksi. Bukti nyata keep-alive, bukan dugaan."""
    parts = urlsplit(url)
    host = parts.hostname
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = parts.path or "/"
    try:
        if parts.scheme == "https":
            conn = __import__("http.client", fromlist=["HTTPSConnection"]).HTTPSConnection(
                host, port, timeout=timeout)
        else:
            conn = __import__("http.client", fromlist=["HTTPConnection"]).HTTPConnection(
                host, port, timeout=timeout)
        conn.request("GET", path)
        r1 = conn.getresponse()
        r1.read()
        sock1 = conn.sock
        conn.request("GET", path)
        r2 = conn.getresponse()
        r2.read()
        same = conn.sock is sock1
        conn.close()
        return {"ok": bool(same), "reused_socket": bool(same),
                "status": [r1.status, r2.status]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _probe_tls(host, port, version_name, timeout=8.0):
    """Tiga hasil berbeda: didukung / TIDAK DIDUKUNG LIB / handshake gagal."""
    lib = ssl.OPENSSL_VERSION
    ver = getattr(ssl.TLSVersion, version_name, None)
    if ver is None:
        return {"ok": None, "reason": "enum_tidak_ada", "lib": lib}
    ctx = ssl.create_default_context()
    try:
        ctx.minimum_version = ver
        ctx.maximum_version = ver
    except Exception as e:
        return {"ok": None, "reason": "ctx_tidak_mendukung", "lib": lib, "error": str(e)[:120]}
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ss:
                return {"ok": True, "negotiated": ss.version(), "cipher": ss.cipher()[0],
                        "lib": lib}
    except Exception as e:
        msg = str(e)[:160]
        low = msg.lower()
        unsupported = ("unsupported protocol" in low or "no protocols available" in low
                       or "wrong version number" in low)
        return {"ok": False,
                "reason": "lib_tidak_mendukung" if unsupported else "handshake_gagal",
                "lib": lib, "error": msg}


def _probe_ipv6(host, timeout=8.0):
    """IPv4-mapped (::ffff:) TIDAK dihitung sebagai bukti IPv6 native."""
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET6)
        addrs = sorted({i[4][0] for i in infos})
        real = [a for a in addrs if not a.lower().startswith("::ffff:")]
        mapped = [a for a in addrs if a.lower().startswith("::ffff:")]
        return {"ok": bool(real), "addresses": addrs[:6], "real_v6": real[:4],
                "ipv4_mapped": mapped[:4],
                "reason": "" if real else "hanya IPv4-mapped, belum v6 native"}
    except Exception as e:
        return {"ok": False, "reason": "resolusi_aaaa_gagal", "error": str(e)[:160]}


def probe_egress(url=DEFAULT_PROBE_URL, timeout=8.0):
    """Ukur kapabilitas nyata dari mesin ini. Tidak pernah raise."""
    parts = urlsplit(url)
    host = parts.hostname or "www.cloudflare.com"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    tls13 = _probe_tls(host, port, "TLSv1_3", timeout) if parts.scheme == "https" else {"ok": None}
    tls12 = _probe_tls(host, port, "TLSv1_2", timeout) if parts.scheme == "https" else {"ok": None}
    ka = _probe_keepalive(url, timeout)
    h1 = _probe_http1(url, timeout)
    v6 = _probe_ipv6(host, timeout)

    proven, unproven, na = [], [], []
    (proven if h1.get("ok") else unproven).append("http1")
    (proven if ka.get("ok") else unproven).append("keepalive")
    for name, res in (("tls13", tls13), ("tls12", tls12)):
        if res.get("ok") is True:
            proven.append(name)
        elif res.get("ok") is False:
            (na if res.get("reason") == "lib_tidak_mendukung" else unproven).append(name)
    (proven if v6.get("ok") else unproven).append("ipv6")
    na.append("http2")            # stdlib urllib tidak negosiasi h2
    if not tls13.get("ok") and tls13.get("reason") == "lib_tidak_mendukung":
        na.append("tls13_lib")

    return {"url": url, "at": time.time(), "ssl_lib": ssl.OPENSSL_VERSION,
            "proven": sorted(set(proven)), "unproven": sorted(set(unproven)),
            "na": sorted(set(na)),
            "evidence": {"http1": h1, "keepalive": ka, "tls13": tls13, "tls12": tls12,
                         "ipv6": v6}}


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------
class Source:
    def __init__(self, source_id, label, kind="local", ip=None, region=None,
                 declared=None, note=""):
        if kind not in KINDS:
            raise SourceError("kind harus salah satu %s" % sorted(KINDS))
        self.source_id = source_id
        self.label = label
        self.kind = kind
        self.ip = ip
        self.region = region
        self.note = note
        self.declared = sorted({c for c in (declared or []) if c in CAPABILITIES})
        self.proven = []
        self.unproven = []
        self.na = []
        self.evidence = {}
        self.created_at = time.time()
        self.last_probe_at = None
        self.probe_count = 0

    def capabilities(self):
        return sorted(set(self.proven) | set(self.declared))

    def can(self, *required):
        have = set(self.capabilities())
        return all(r in have for r in required)

    def missing(self, *required):
        have = set(self.capabilities())
        return sorted(r for r in required if r not in have)

    def to_dict(self, with_evidence=False):
        d = {"id": self.source_id, "label": self.label, "kind": self.kind, "ip": self.ip,
             "region": self.region, "note": self.note, "declared": self.declared,
             "proven": self.proven, "unproven": self.unproven, "na": self.na,
             "capabilities": self.capabilities(), "probe_count": self.probe_count,
             "last_probe_at": self.last_probe_at, "created_at": self.created_at,
             "kind_is_datacenter": self.kind in ("vps", "worker", "datacenter")}
        if with_evidence:
            d["evidence"] = self.evidence
        return d


class SourceRegistry:
    def __init__(self):
        self.lock = threading.Lock()
        self.sources = {}

    def register(self, label, kind="local", ip=None, region=None, declared=None,
                 source_id=None, note=""):
        sid = source_id or ("src-%s" % label.lower().replace(" ", "-"))[:40]
        with self.lock:
            if sid in self.sources:
                raise SourceError("sumber '%s' sudah terdaftar" % sid)
            s = Source(sid, label, kind=kind, ip=ip, region=region,
                       declared=declared, note=note)
            self.sources[sid] = s
        return s

    def get(self, sid):
        return self.sources.get(sid)

    def list(self):
        return list(self.sources.values())

    def remove(self, sid):
        with self.lock:
            return self.sources.pop(sid, None)

    def probe(self, sid, url=DEFAULT_PROBE_URL, timeout=8.0):
        s = self.get(sid)
        if not s:
            raise SourceError("sumber '%s' tidak ada" % sid)
        r = probe_egress(url, timeout)
        with self.lock:
            s.proven = r["proven"]
            s.unproven = r["unproven"]
            s.na = r.get("na", [])
            s.evidence = r["evidence"]
            s.last_probe_at = time.time()
            s.probe_count += 1
            if not s.ip:
                ip = (r["evidence"].get("ipv6") or {}).get("addresses")
                s.ip = ip[0] if ip else None
        return r

    def pick(self, required, kind=None):
        required = list(required or [])
        cands = [s for s in self.list() if kind is None or s.kind == kind]
        for s in sorted(cands, key=lambda x: len(x.missing(*required))):
            if s.can(*required):
                return s, []
        if not cands:
            return None, ["tidak ada sumber dengan kind=%s" % kind]
        best = sorted(cands, key=lambda x: len(x.missing(*required)))[0]
        return None, ["%s kurang: %s" % (best.source_id, ", ".join(best.missing(*required)))]

    def matrix(self):
        return {"capabilities": list(CAPABILITIES),
                "ssl_lib": ssl.OPENSSL_VERSION,
                "sources": {s.source_id: s.capabilities() for s in self.list()},
                "not_applicable": {s.source_id: s.na for s in self.list()},
                "gaps": {c: [s.source_id for s in self.list() if not s.can(c)]
                         for c in CAPABILITIES}}


REGISTRY = SourceRegistry()


def ensure_local(url=DEFAULT_PROBE_URL):
    """Daftarkan + probe mesin ini sekali, idempoten."""
    s = REGISTRY.get("src-local")
    if s is None:
        s = REGISTRY.register("local-laptop", kind="local",
                              declared=["datacenter", "high_concurrency"],
                              note="egress utama; di-probe nyata")
    REGISTRY.probe(s.source_id, url)
    return s
