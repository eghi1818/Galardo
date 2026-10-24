"""Galardo - ingest intel (HIPOTESIS) + pre-flight validasi.

Doktrin yang mengikat modul ini:
  * Intel dari pihak ketiga (mis. REA) = HIPOTESIS, bukan fakta.
  * Galardo = PENGUKURAN. Setiap divergensi klaim vs hasil ukur WAJIB muncul di keluaran.
  * Tidak menyentuh jaringan saat import (pelajaran #17). Semua fetch dibungkus try/except
    dan selalu punya jalur SKIP (pelajaran #14).
"""

from __future__ import annotations

import json
import re

__all__ = [
    "parse",
    "normalize_host",
    "normalize_ip",
    "divergences",
    "ringkasan",
    "preflight",
    "measured_from",
    "describe",
    "errors",
    "FIELDS_DIBANDING",
    "VERDICT_COCOK",
    "VERDICT_BEDA",
    "VERDICT_TAK_DIKLAIM",
    "VERDICT_TAK_TERUKUR",
]

try:  # dependensi internal; modul tetap bisa diimpor sendirian
    from . import origins as _origins
except Exception:
    try:
        import origins as _origins  # type: ignore
    except Exception:
        _origins = None

try:
    from . import egress as _egress
except Exception:
    try:
        import egress as _egress  # type: ignore
    except Exception:
        _egress = None


FIELD_ALIASES = {
    "domain": ("domain", "host", "hostname", "situs", "target", "domain_target"),
    "origins": ("origin", "origins", "origin_ip", "ip_origin", "origin_host", "backend", "backend_ip"),
    "edge": ("edge", "cdn", "ns", "nameserver", "nameservers", "dns", "dns_provider"),
    "waf": ("waf", "waf_provider", "firewall", "pelindung", "proteksi"),
    "asn": ("asn", "asn_egress", "as_number", "asn_origin"),
    "egress": ("egress", "egress_ips", "egress_ip", "ip_egress", "sumber_egress"),
    "rate": ("rate", "rate_limit", "limit", "rps", "qps"),
    "notes": ("notes", "note", "catatan", "keterangan", "komentar"),
    "source": ("source", "sumber", "dari", "asal"),
}

FIELDS_DIBANDING = ("origins", "edge", "waf", "asn", "egress")

VERDICT_COCOK = "cocok"
VERDICT_BEDA = "beda"
VERDICT_TAK_DIKLAIM = "tidak diklaim"
VERDICT_TAK_TERUKUR = "tak terukur"

_SPLIT = re.compile(r"[,\s;|]+")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
_IPV4 = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")

_SCALAR = ("domain", "waf", "rate", "notes", "source")


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            out.extend(_as_list(item))
        return out
    return [p for p in _SPLIT.split(str(value)) if p.strip()]


def _leaves(value):
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            out.extend(_leaves(k))
            out.extend(_leaves(v))
        return out
    if isinstance(value, (list, tuple, set)):
        out = []
        for v in value:
            out.extend(_leaves(v))
        return out
    if value is None:
        return []
    return [str(value)]


def _first(d, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def normalize_host(value):
    """lowercase, buang skema/port/path/query, buang titik ekor. None bila kosong."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    s = _SCHEME.sub("", s)
    s = s.split("/", 1)[0]
    s = s.split("?", 1)[0]
    if not s.startswith("["):
        s = s.split(":", 1)[0]
    s = s.strip().rstrip(".")
    return s or None


def normalize_ip(value):
    """IPv4 -> bentuk ternormalisasi; None bila bukan IPv4 valid."""
    if value is None:
        return None
    s = str(value).strip()
    m = _IPV4.match(s)
    if not m:
        return None
    for part in m.groups():
        if int(part) > 255:
            return None
    return ".".join(str(int(p)) for p in m.groups())


def _hosts_in(value):
    out = set()
    for leaf in _leaves(value):
        for token in _as_list(leaf):
            h = normalize_host(token)
            if h and ("." in h or _IPV4.match(h)):
                out.add(h)
    return sorted(out)


def _norm_set(values):
    out = set()
    for item in _as_list(values):
        h = normalize_host(item)
        if h:
            out.add(h)
    return out


def _canon_key(key):
    k = str(key).strip().lower().replace("-", "_").replace(" ", "_")
    for field, aliases in FIELD_ALIASES.items():
        if k == field or k in aliases:
            return field
    return k


def parse(payload):
    """dict | JSON string | teks 'key: value' per baris -> intel ternormalisasi."""
    raw = {}
    if payload is None:
        payload = {}
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", "replace")
    if isinstance(payload, str):
        s = payload.strip()
        if not s:
            raw = {}
        elif s[0] in "{[":
            try:
                loaded = json.loads(s)
            except ValueError:
                raise ValueError("payload terlihat JSON tapi gagal diurai")
            if not isinstance(loaded, dict):
                raise ValueError("payload JSON harus berupa objek")
            raw = dict(loaded)
        else:
            for line in s.splitlines():
                line = line.strip()
                if line.startswith(("-", "*")):
                    line = line[1:].strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    k, v = line.split(":", 1)
                elif "=" in line:
                    k, v = line.split("=", 1)
                else:
                    continue
                raw[k.strip()] = v.strip()
    elif isinstance(payload, dict):
        raw = dict(payload)
    else:
        raise ValueError("payload tidak dikenali: %s" % type(payload).__name__)

    merged = {}
    for k, v in raw.items():
        ck = _canon_key(k)
        if ck in _SCALAR:
            merged[ck] = v
        else:
            merged.setdefault(ck, [])
            merged[ck].extend(_as_list(v))

    return {
        "domain": normalize_host(merged.get("domain")),
        "origins": merged.get("origins") or [],
        "edge": merged.get("edge") or [],
        "waf": (str(merged["waf"]).strip() or None) if merged.get("waf") else None,
        "asn": merged.get("asn") or [],
        "egress": merged.get("egress") or [],
        "rate": merged.get("rate"),
        "notes": merged.get("notes"),
        "source": merged.get("source") or "intel",
        "raw": raw,
    }


def errors(payload):
    intel = parse(payload)
    out = []
    if not intel.get("domain"):
        out.append("domain belum ada (wajib untuk pengukuran)")
    if not intel.get("origins"):
        out.append("klaim origin belum ada")
    return out


def measured_from(domain=None, probe=False):
    """Ukur nyata (best-effort). Gagal -> None + alasan di 'sumber'. Tidak pernah melempar."""
    out = {"origins": None, "edge": None, "waf": None, "asn": None, "egress": None, "sumber": {}}

    if _origins is not None and domain:
        try:
            fn = getattr(_origins, "candidates", None)
            if callable(fn):
                try:
                    cand = fn(domain, probe=probe)
                except TypeError:
                    cand = fn(domain)
                if isinstance(cand, dict):
                    out["origins"] = _hosts_in(_first(cand, ("origins", "origin", "kandidat", "candidates", "hosts", "host")))
                    out["edge"] = _hosts_in(_first(cand, ("edge", "edges", "cdn", "edge_hosts")))
                    out["waf"] = _first(cand, ("waf", "waf_provider"))
                else:
                    out["origins"] = _hosts_in(cand)
                out["sumber"]["origins"] = "origins.candidates"
        except Exception as exc:
            out["sumber"]["origins"] = "gagal: %s" % exc

    if _egress is not None:
        try:
            fn = getattr(_egress, "snapshot", None) or getattr(_egress, "proxies", None)
            if callable(fn):
                out["egress"] = _hosts_in(fn())
                out["sumber"]["egress"] = "egress.%s" % getattr(fn, "__name__", "snapshot")
        except Exception as exc:
            out["sumber"]["egress"] = "gagal: %s" % exc

    return out


def _catatan(field, verdict, klaim, ukur):
    if verdict == VERDICT_BEDA:
        hanya_klaim = sorted(klaim - ukur)
        hanya_ukur = sorted(ukur - klaim)
        bagian = []
        if hanya_klaim:
            bagian.append("diklaim tapi tak terlihat: %s" % ", ".join(hanya_klaim))
        if hanya_ukur:
            bagian.append("terukur tapi tak diklaim: %s" % ", ".join(hanya_ukur))
        return "; ".join(bagian)
    if verdict == VERDICT_TAK_TERUKUR:
        return "klaim ada, pengukuran kosong/gagal -> wajib diukur ulang"
    if verdict == VERDICT_TAK_DIKLAIM:
        return "tidak ada klaim dari intel"
    return "klaim selaras dengan pengukuran"


def divergences(intel, measured):
    measured = measured or {}
    rows = []
    for field in FIELDS_DIBANDING:
        klaim = _norm_set(intel.get(field))
        ukur = _norm_set(measured.get(field))
        if not klaim:
            verdict = VERDICT_TAK_DIKLAIM
        elif not ukur:
            verdict = VERDICT_TAK_TERUKUR
        elif klaim == ukur:
            verdict = VERDICT_COCOK
        else:
            verdict = VERDICT_BEDA
        rows.append({
            "field": field,
            "klaim": sorted(klaim),
            "pengukuran": sorted(ukur),
            "verdict": verdict,
            "catatan": _catatan(field, verdict, klaim, ukur),
        })
    return rows


def ringkasan(rows):
    counts = {"total": len(rows)}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    counts["cocok"] = counts.get(VERDICT_COCOK, 0)
    counts["beda"] = counts.get(VERDICT_BEDA, 0)
    counts["tak_terukur"] = counts.get(VERDICT_TAK_TERUKUR, 0)
    counts["tak_diklaim"] = counts.get(VERDICT_TAK_DIKLAIM, 0)
    counts["selaras"] = counts["cocok"] + counts["tak_diklaim"]
    counts["tidak_selaras"] = counts["beda"] + counts["tak_terukur"]
    return counts


def preflight(payload, measured=None, probe=False, ukur=True):
    intel = parse(payload)
    if measured is None:
        measured = measured_from(intel.get("domain"), probe=probe) if ukur else {}
    rows = divergences(intel, measured)
    return {
        "domain": intel.get("domain"),
        "intel": intel,
        "pengukuran": measured,
        "divergensi": rows,
        "ringkasan": ringkasan(rows),
        "catatan": "intel = HIPOTESIS, pengukuran = Galardo; divergensi wajib dicatat",
        "catatan_intel": errors(intel),
    }


def describe():
    return {
        "field_dibanding": list(FIELDS_DIBANDING),
        "verdict": [VERDICT_COCOK, VERDICT_BEDA, VERDICT_TAK_DIKLAIM, VERDICT_TAK_TERUKUR],
        "alias": {k: list(v) for k, v in FIELD_ALIASES.items()},
        "prinsip": "intel = hipotesis, pengukuran = Galardo, divergensi dicatat",
    }
