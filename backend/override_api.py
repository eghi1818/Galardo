"""Galardo - adaptor override edge (Goal 3). Memakai API SEBENARNYA routeoverride.

API yang benar (dari inspeksi, bukan tebakan):
  RouteOverrider.apply(spec=None, tiers=None) ; revert(spec_id=None) ; probe(spec_id, path=None)
  OverrideSpec(origin, paths, mode, spec_id, shim_port, tiers, upstream, host_header, port, label, hosts, note)
Kontrak: tidak pernah melempar; selalu kembalikan dict + catatan. `forced` dibuktikan lewat probe.
"""
from __future__ import annotations

try:
    from . import routeoverride as _ro
except Exception:
    try:
        import routeoverride as _ro  # type: ignore
    except Exception:
        _ro = None

HEADER = getattr(_ro, "OVERRIDE_HEADER", "X-Galardo-Override")
MODE = ("404", "410", "503", "blank")

# nama tier sebenarnya: T1/T2/T3 (stats.tier_order = T2,T1,T3 -> local-first)
ALIAS_TIER = {"local": "T2", "shim": "T2", "hosts": "T1", "host": "T1",
              "edge": "T3", "cloudflare": "T3", "cf": "T3", "auto": None}

__all__ = ["HEADER", "MODE", "ada_mesin", "status", "terapkan", "bersihkan", "probe", "describe"]


def ada_mesin():
    return _ro is not None


def _target():
    obj = getattr(_ro, "REGISTRY", None) if _ro is not None else None
    return obj if obj is not None else _ro


def _fn(*nama):
    for sumber in (_target(), _ro):
        if sumber is None:
            continue
        for n in nama:
            f = getattr(sumber, n, None)
            if callable(f):
                return f, n
    return None, None


def _tier(nama):
    """Petakan alias ke nama tier sebenarnya (T1/T2/T3). None = biarkan default (auto)."""
    if not nama:
        return None
    t = str(nama).strip().upper()
    if t in ("T1", "T2", "T3"):
        return t
    return ALIAS_TIER.get(str(nama).strip().lower())


def _normal(domain):
    d = str(domain or "").strip()
    if not d:
        return d
    return d if "://" in d else "https://" + d


def _spec(domain, mode, tier=None, paths=None, label=""):
    if _ro is None or not hasattr(_ro, "OverrideSpec"):
        return None
    kw = {"origin": _normal(domain), "mode": mode or "404", "label": label or ("galardo:" + str(domain))}
    if paths:
        kw["paths"] = list(paths)
    t = _tier(tier)
    if t:
        kw["tiers"] = [t]
    try:
        return _ro.OverrideSpec(**kw)
    except Exception:
        try:
            return _ro.OverrideSpec(_normal(domain), mode or "404")
        except Exception:
            return None


def _panggil(f, kandidat):
    for args, kw in kandidat:
        try:
            return f(*args, **kw), "args=%d" % len(args), None
        except TypeError:
            continue
        except Exception as exc:
            return None, None, repr(exc)
    return None, None, "semua bentuk argumen gagal"


def _spec_id(hasil, spec=None):
    if isinstance(hasil, dict):
        for k in ("spec_id", "id", "spesifikasi"):
            if hasil.get(k):
                return str(hasil[k])
    if spec is not None:
        v = getattr(spec, "spec_id", None)
        if v:
            return str(v)
    if isinstance(hasil, (list, tuple)) and hasil:
        return _spec_id(hasil[0])
    return None


def status():
    out = {"ada_mesin": ada_mesin(), "header": HEADER, "mode_tersedia": list(MODE),
           "aktif": None, "stats": None, "sumber": None, "catatan": None}
    if not ada_mesin():
        out["catatan"] = "routeoverride tidak tersedia"
        return out
    f, nama = _fn("list_active")
    if f is not None:
        hasil, _, err = _panggil(f, [((), {})])
        out["aktif"] = hasil
        out["sumber"] = nama
        out["catatan"] = err
    g, nama2 = _fn("stats")
    if g is not None:
        hasil, _, _ = _panggil(g, [((), {})])
        out["stats"] = hasil
    if out["sumber"] is None:
        out["catatan"] = "list_active tidak ditemukan"
    return out


def terapkan(domain, mode="404", tier=None, paths=None):
    out = {"domain": domain, "mode": mode, "tier": tier, "header": HEADER, "spec_id": None,
           "hasil": None, "sumber": None, "catatan": None, "probe": None, "forced": None}
    if not ada_mesin():
        out["catatan"] = "routeoverride tidak tersedia"
        return out
    spec = _spec(domain, mode, tier, paths)
    if spec is None:
        out["catatan"] = "OverrideSpec tidak bisa dibuat"
        return out
    f, nama = _fn("apply")
    if f is None:
        out["catatan"] = "metode apply tidak ditemukan"
        return out
    kandidat = [((spec,), {})]
    _t = _tier(tier)
    if _t:
        kandidat.append(((spec,), {"tiers": [_t]}))
    hasil, _, err = _panggil(f, kandidat)
    if hasil is None:
        prep, _pn = _fn("prepare")
        if prep is not None:
            _panggil(prep, [((spec,), {})])
            hasil, _, err = _panggil(f, kandidat)
    out.update({"hasil": hasil, "sumber": nama, "catatan": err})
    out["spec_id"] = _spec_id(hasil, spec)
    if out["spec_id"]:
        p = probe(out["spec_id"])
        out["probe"] = p.get("probe")
        out["forced"] = p.get("forced")
    return out


def bersihkan(spec_id=None):
    out = {"spec_id": spec_id, "header": HEADER, "hasil": None, "sumber": None, "catatan": None}
    if not ada_mesin():
        out["catatan"] = "routeoverride tidak tersedia"
        return out
    f, nama = _fn("revert")
    if f is None:
        out["catatan"] = "metode revert tidak ditemukan"
        return out
    kandidat = [((spec_id,), {})] if spec_id else [((), {}), ((None,), {})]
    hasil, _, err = _panggil(f, kandidat)
    out.update({"hasil": hasil, "sumber": nama, "catatan": err})
    return out


def probe(spec_id, path=None):
    out = {"spec_id": spec_id, "path": path, "header": HEADER, "probe": None, "forced": None, "catatan": None}
    if not ada_mesin():
        out["catatan"] = "routeoverride tidak tersedia"
        return out
    f, nama = _fn("probe")
    if f is None:
        out["catatan"] = "metode probe tidak ditemukan"
        return out
    kandidat = [((spec_id,), {})] if path is None else [((spec_id, path), {}), ((spec_id,), {"path": path})]
    hasil, _, err = _panggil(f, kandidat)
    out["probe"] = hasil
    out["catatan"] = err
    if isinstance(hasil, dict):
        out["forced"] = hasil.get("forced")
        if out["forced"] is None:
            out["forced"] = hasil.get("override_header") is not None
    return out


def describe():
    return {"header_pembeda": HEADER, "mode": list(MODE), "ada_mesin": ada_mesin(),
            "target_objek": type(_target()).__name__ if _target() is not None else None,
            "api": ["apply(spec)", "revert(spec_id)", "probe(spec_id)"],
            "prinsip": "404 kita selalu bertanda %s supaya tidak tertukar 404 asli" % HEADER}
