"""Galardo - runner falsifikasi: uji yang HARUS konsisten dengan verdict.

Uji yang gagal bukan error program, tapi TEMUAN: verdict dan saksi saling bertentangan.
Kesimpulan: TIDAK_TERFALSIFIKASI hanya sah bila uji lolos DAN saksi >= 3 jaringan.
"""
from __future__ import annotations

__all__ = ["UJI", "jalankan", "describe"]

MIN_JARINGAN = 3


def _s(saksi, k):
    v = (saksi or {}).get(k)
    return v if isinstance(v, dict) else {}


def _ok(saksi, k):
    return _s(saksi, k).get("ok") is True


def _gagal(saksi, k):
    return _s(saksi, k).get("ok") is False


def _status(saksi):
    return _s(saksi, "http").get("status")


def u1_modyar(saksi, v):
    if v.get("mode") != "MODYAR":
        return (True, "bukan MODYAR")
    return (_gagal(saksi, "dns") and _gagal(saksi, "tcp") and _gagal(saksi, "tls"),
            "MODYAR wajib didukung: DNS + TCP + TLS semuanya gagal")


def u2_dns(saksi, v):
    if v.get("mode") != "DNS_MATI":
        return (True, "bukan DNS_MATI")
    return (_gagal(saksi, "dns"), "DNS_MATI wajib didukung saksi DNS gagal")


def u3_net(saksi, v):
    if v.get("mode") != "NET_MATI":
        return (True, "bukan NET_MATI")
    return (_gagal(saksi, "tcp") and _ok(saksi, "dns"), "NET_MATI: TCP gagal TAPI DNS harus hidup")


def u4_tls(saksi, v):
    if v.get("mode") != "TLS_MATI":
        return (True, "bukan TLS_MATI")
    return (_gagal(saksi, "tls") and _ok(saksi, "tcp"), "TLS_MATI: TLS gagal TAPI TCP harus terbuka")


def u5_edge(saksi, v):
    if v.get("mode") != "EDGE_MATI":
        return (True, "bukan EDGE_MATI")
    return (_s(saksi, "http").get("ciri_edge") is True, "EDGE_MATI wajib ada ciri halaman edge")


def u6_origin(saksi, v):
    if v.get("mode") != "ORIGIN_MATI":
        return (True, "bukan ORIGIN_MATI")
    st = _status(saksi)
    return (isinstance(st, int) and (st >= 500 or st in (521, 522, 523, 524, 504)),
            "ORIGIN_MATI wajib 5xx / 522 / 504")


def u7_konten(saksi, v):
    if v.get("mode") != "KONTEN_HILANG":
        return (True, "bukan KONTEN_HILANG")
    return (_status(saksi) in (404, 410), "KONTEN_HILANG wajib 404/410")


def u8_soft(saksi, v):
    if v.get("mode") != "SOFT_404":
        return (True, "bukan SOFT_404")
    return (_status(saksi) == 200 and _s(saksi, "http").get("ciri_parkir") is True,
            "SOFT_404 wajib 200 + ciri halaman parkir")


def u9_override(saksi, v):
    if v.get("mode") != "MATI_OVERRIDE":
        return (True, "bukan MATI_OVERRIDE")
    return ((saksi or {}).get("override") is True, "MATI_OVERRIDE wajib didukung flag override")


def u10_hidup(saksi, v):
    if v.get("mode") != "HIDUP":
        return (True, "bukan HIDUP")
    st = _status(saksi)
    return (_ok(saksi, "dns") and _ok(saksi, "tcp") and isinstance(st, int) and st < 400,
            "HIDUP wajib didukung semua lapisan hidup")


UJI = [
    ("MODYAR butuh semua lapisan gagal", u1_modyar),
    ("DNS_MATI butuh saksi DNS gagal", u2_dns),
    ("NET_MATI: TCP gagal tapi DNS hidup", u3_net),
    ("TLS_MATI: TLS gagal tapi TCP terbuka", u4_tls),
    ("EDGE_MATI butuh ciri halaman edge", u5_edge),
    ("ORIGIN_MATI butuh 5xx/522/504", u6_origin),
    ("KONTEN_HILANG butuh 404/410", u7_konten),
    ("SOFT_404 butuh 200 + ciri parkir", u8_soft),
    ("MATI_OVERRIDE butuh flag override", u9_override),
    ("HIDUP butuh semua lapisan hidup", u10_hidup),
]


def jalankan(verdict, saksi=None):
    baris = []
    for nama, fn in UJI:
        try:
            konsisten, catatan = fn(saksi or {}, verdict or {})
        except Exception as exc:
            konsisten, catatan = False, "uji error: %r" % exc
        baris.append({"uji": nama, "konsisten": bool(konsisten), "catatan": catatan})
    gagal = [b for b in baris if not b["konsisten"]]
    jaringan = (saksi or {}).get("jaringan") or []
    if len(jaringan) < MIN_JARINGAN:
        kesimpulan = "belum_konklusif"
    elif gagal:
        kesimpulan = "TERFALSI"
    else:
        kesimpulan = "TIDAK_TERFALSIFIKASI"
    return {"uji": baris, "jumlah": len(baris), "konsisten": len(baris) - len(gagal),
            "gagal": len(gagal), "jaringan": len(jaringan), "min_jaringan": MIN_JARINGAN,
            "kesimpulan": kesimpulan}


def describe():
    return {"jumlah_uji": len(UJI), "min_jaringan": MIN_JARINGAN,
            "prinsip": "uji gagal = temuan; belum_konklusif bila saksi < 3 jaringan"}
