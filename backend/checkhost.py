"""Galardo - check-host per-negara: bukti target MATI/HIDUP dari banyak titik dunia.

Inti (parsing + agregasi) murni offline-testable; hanya probe()/mulai()/ambil() menyentuh jaringan.
Aturan repo: semua fetch HTTPS backend WAJIB memakai context netssl.
Sumber: check-host.net (check-http) - hipotesis pihak ketiga, hasilnya tetap bukti pengukuran.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from . import netssl as _ns
except Exception:
    try:
        import netssl as _ns  # type: ignore
    except Exception:
        _ns = None

BASE = "https://check-host.net"
UA = "galardo-checkhost/1"

__all__ = [
    "normalize_url", "parse_nodes", "parse_hasil", "grup_negara", "ringkas",
    "mulai", "ambil", "tunggu", "probe", "describe",
]


def _ctx():
    return _ns.context() if _ns is not None else None


def normalize_url(url):
    if url is None:
        return None
    s = str(url).strip()
    if not s:
        return None
    if "://" not in s:
        s = "https://" + s
    return s


def _get_json(path, timeout=8.0):
    req = urllib.request.Request(BASE + path, headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def parse_nodes(payload):
    """{'us1.node.check-host.net': ['us','New York',...]} -> {node: {negara, kota, host}}"""
    out = {}
    for host, info in ((payload or {}).get("nodes") or {}).items():
        if isinstance(info, (list, tuple)) and info:
            out[host] = {"negara": str(info[0]).lower(), "kota": (str(info[1]) if len(info) > 1 else ""), "host": host}
        else:
            out[host] = {"negara": "??", "kota": "", "host": host}
    return out


def parse_hasil(payload):
    """check-result -> {node: {ok: bool|None, waktu: float|None, err: str|None}}"""
    out = {}
    for host, info in (payload or {}).items():
        if info is None:
            out[host] = {"ok": None, "waktu": None, "err": "belum siap"}
            continue
        entri = info[0] if isinstance(info, list) and info and isinstance(info[0], list) else info
        if not isinstance(entri, list) or not entri:
            out[host] = {"ok": None, "waktu": None, "err": "format tak dikenal"}
            continue
        if entri[0] == 1:
            waktu = None
            for x in entri[1:]:
                if isinstance(x, (int, float)) and not isinstance(x, bool):
                    waktu = float(x)
                    break
            out[host] = {"ok": True, "waktu": waktu, "err": None}
        else:
            pesan = next((str(x) for x in entri[1:] if isinstance(x, str)), "gagal")
            out[host] = {"ok": False, "waktu": None, "err": pesan}
    return out


def grup_negara(nodes, hasil):
    """Gabungkan info node + hasil menjadi baris per-negara (terurut)."""
    baris = []
    for host, info in (nodes or {}).items():
        h = (hasil or {}).get(host) or {"ok": None, "waktu": None, "err": "belum ada hasil"}
        baris.append({
            "negara": info.get("negara") or "??",
            "kota": info.get("kota") or "",
            "node": host,
            "ok": h.get("ok"),
            "waktu": h.get("waktu"),
            "err": h.get("err"),
        })
    baris.sort(key=lambda b: (b["negara"], b["kota"], b["node"]))
    return baris


def ringkas(baris):
    negara = {}
    ok = gagal = belum = 0
    for b in baris:
        n = negara.setdefault(b["negara"], {"ok": 0, "gagal": 0, "belum": 0})
        if b["ok"] is True:
            ok += 1
            n["ok"] += 1
        elif b["ok"] is False:
            gagal += 1
            n["gagal"] += 1
        else:
            belum += 1
            n["belum"] += 1
    total = len(baris)
    if total == 0:
        verdict = "tanpa node"
    elif belum == total:
        verdict = "belum ada hasil"
    elif gagal == total:
        verdict = "MATI dari %d/%d negara" % (gagal, total)
    elif ok == total:
        verdict = "HIDUP dari %d/%d negara" % (ok, total)
    else:
        verdict = "SEBAGIAN: %d hidup / %d mati / %d belum dari %d negara" % (ok, gagal, belum, total)
    return {"total": total, "ok": ok, "gagal": gagal, "belum": belum, "negara": negara, "verdict": verdict}


def mulai(url, max_nodes=5, timeout=8.0):
    u = normalize_url(url)
    if not u:
        raise ValueError("url kosong")
    p = _get_json("/check-http?host=%s&max_nodes=%d" % (urllib.parse.quote(u, safe=""), int(max_nodes)), timeout)
    return {"url": u, "request_id": p.get("request_id"), "nodes": parse_nodes(p), "tautan": p.get("permanent_link")}


def ambil(request_id, timeout=8.0):
    return parse_hasil(_get_json("/check-result/%s" % request_id, timeout))


def tunggu(request_id, batas=12.0, jeda=1.0):
    t0 = time.time()
    hasil = {}
    while time.time() - t0 < batas:
        hasil = ambil(request_id)
        if hasil and all(v.get("ok") is not None for v in hasil.values()):
            return hasil, {"lengkap": True, "detik": round(time.time() - t0, 2)}
        time.sleep(jeda)
    return hasil, {"lengkap": bool(hasil) and all(v.get("ok") is not None for v in hasil.values()),
                   "detik": round(time.time() - t0, 2)}


def probe(url, max_nodes=5, batas=12.0, timeout=8.0):
    """Cek url dari banyak negara. Tidak pernah melempar: kegagalan jaringan -> 'catatan'."""
    out = {"url": normalize_url(url), "request_id": None, "nodes": {}, "hasil": {},
           "baris": [], "ringkasan": ringkas([]), "catatan": None, "mulai_detik": None}
    try:
        t0 = time.time()
        m = mulai(url, max_nodes=max_nodes, timeout=timeout)
        out["request_id"] = m["request_id"]
        out["nodes"] = m["nodes"]
        out["tautan"] = m.get("tautan")
        hasil, info = tunggu(m["request_id"], batas=batas)
        out["hasil"] = hasil
        out["mulai_detik"] = round(time.time() - t0, 2)
        out["baris"] = grup_negara(out["nodes"], hasil)
        out["ringkasan"] = ringkas(out["baris"])
        out["catatan"] = "lengkap" if info["lengkap"] else "sebagian (batas waktu tercapai)"
    except Exception as exc:
        out["catatan"] = "gagal jaringan: %s" % exc
    return out


def describe():
    return {
        "sumber": "check-host.net (check-http)",
        "keluaran": ["url", "nodes", "baris", "ringkasan.verdict", "catatan"],
        "prinsip": "bukti MATI/HIDUP dari banyak negara; node pihak ketiga = hipotesis yang diukur",
    }
