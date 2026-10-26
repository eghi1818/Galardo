"""Galardo - adaptor override edge (Goal 3). Membungkus routeoverride tanpa menebak nama fungsi.

Kontrak: semua fungsi TIDAK pernah melempar; selalu mengembalikan dict + catatan.
Header pembeda (OVERRIDE_HEADER) selalu dilaporkan supaya bukti tidak tertukar dengan 404 asli.
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

__all__ = ["HEADER", "MODE", "ada_mesin", "status", "terapkan", "bersihkan", "describe"]


def ada_mesin():
    return _ro is not None


def _fn(*nama):
    if _ro is None:
        return None, None
    for n in nama:
        f = getattr(_ro, n, None)
        if callable(f):
            return f, n
    return None, None


def _panggil(f, kandidat_arg):
    for args in kandidat_arg:
        try:
            return f(*args), "arg%d" % len(args), None
        except TypeError:
            continue
        except Exception as exc:
            return None, None, repr(exc)
    return None, None, "semua bentuk argumen gagal"


def status(domain=None):
    out = {"ada_mesin": ada_mesin(), "header": HEADER, "mode_tersedia": list(MODE),
           "domain": domain, "status": None, "sumber": None, "catatan": None}
    if not ada_mesin():
        out["catatan"] = "routeoverride tidak tersedia"
        return out
    f, nama = _fn("status", "keadaan", "info", "state", "lihat")
    if f is None:
        out["catatan"] = "fungsi status tidak ditemukan (lihat .out)"
        return out
    hasil, ket, err = _panggil(f, [(domain,), ()])
    out["status"] = hasil
    out["sumber"] = nama
    out["catatan"] = ket or err
    return out


def terapkan(domain, mode="404"):
    out = {"domain": domain, "mode": mode, "header": HEADER, "hasil": None, "sumber": None, "catatan": None}
    if not ada_mesin():
        out["catatan"] = "routeoverride tidak tersedia"
        return out
    f, nama = _fn("terapkan", "apply", "aktifkan", "force", "pasang", "set_override", "override")
    if f is None:
        out["catatan"] = "fungsi apply tidak ditemukan"
        return out
    hasil, ket, err = _panggil(f, [(domain, mode), (domain,), (mode, domain)])
    out["hasil"] = hasil
    out["sumber"] = nama
    out["catatan"] = ket or err
    return out


def bersihkan(domain=None):
    out = {"domain": domain, "header": HEADER, "hasil": None, "sumber": None, "catatan": None}
    if not ada_mesin():
        out["catatan"] = "routeoverride tidak tersedia"
        return out
    f, nama = _fn("bersihkan", "clear", "hapus", "reset", "matikan", "unset", "lepas")
    if f is None:
        out["catatan"] = "fungsi clear tidak ditemukan"
        return out
    hasil, ket, err = _panggil(f, [(domain,), ()])
    out["hasil"] = hasil
    out["sumber"] = nama
    out["catatan"] = ket or err
    return out


def describe():
    return {"header_pembeda": HEADER, "mode": list(MODE), "ada_mesin": ada_mesin(),
            "prinsip": "404 kita selalu bertanda %s supaya tidak tertukar 404 asli" % HEADER}
