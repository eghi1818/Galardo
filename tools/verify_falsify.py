#!/usr/bin/env python3
"""Verifier behavioral runner falsifikasi: tiap mode konsisten lolos; saksi salah -> TERFALSI."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import falsify as F  # noqa: E402

PASS = 0
FAIL = 0


def cek(nama, kondisi, detail=""):
    global PASS, FAIL
    if kondisi:
        PASS += 1
        print("  [ok]   %s" % nama)
    else:
        FAIL += 1
        print("  [GAGAL] %s  %s" % (nama, detail))


SAKSI_OK = {
    "dns": {"ok": True}, "tcp": {"ok": True}, "tls": {"ok": True},
    "http": {"status": 200}, "jaringan": ["asn-a", "asn-b", "asn-c"], "override": False,
}


def saksi(mode):
    s = {"dns": dict(SAKSI_OK["dns"]), "tcp": dict(SAKSI_OK["tcp"]), "tls": dict(SAKSI_OK["tls"]),
         "http": dict(SAKSI_OK["http"]), "jaringan": list(SAKSI_OK["jaringan"]), "override": False}
    if mode == "MODYAR":
        s["dns"]["ok"] = False; s["tcp"]["ok"] = False; s["tls"]["ok"] = False
    elif mode == "DNS_MATI":
        s["dns"]["ok"] = False
    elif mode == "NET_MATI":
        s["tcp"]["ok"] = False
    elif mode == "TLS_MATI":
        s["tls"]["ok"] = False
    elif mode == "EDGE_MATI":
        s["http"] = {"status": 502, "ciri_edge": True}
    elif mode == "ORIGIN_MATI":
        s["http"] = {"status": 522}
    elif mode == "KONTEN_HILANG":
        s["http"] = {"status": 404}
    elif mode == "SOFT_404":
        s["http"] = {"status": 200, "ciri_parkir": True}
    elif mode == "MATI_OVERRIDE":
        s["override"] = True
    return s


def main():
    print("== verify_falsify (offline) ==")
    cek("10 uji terdaftar", len(F.UJI) == 10, repr(len(F.UJI)))
    for mode in ("HIDUP", "MODYAR", "DNS_MATI", "NET_MATI", "TLS_MATI", "EDGE_MATI",
                 "ORIGIN_MATI", "KONTEN_HILANG", "SOFT_404", "MATI_OVERRIDE"):
        h = F.jalankan({"mode": mode}, saksi(mode))
        cek("%s: konsisten + TIDAK_TERFALSIFIKASI" % mode,
            h["gagal"] == 0 and h["kesimpulan"] == "TIDAK_TERFALSIFIKASI", repr(h["kesimpulan"]))

    h = F.jalankan({"mode": "DNS_MATI"}, {**saksi("DNS_MATI"), "dns": {"ok": True}})
    cek("saksi bertentangan -> TERFALSI", h["kesimpulan"] == "TERFALSI" and h["gagal"] >= 1, repr(h["kesimpulan"]))

    s2 = dict(saksi("MODYAR")); s2["jaringan"] = ["a", "b"]
    cek("saksi < 3 jaringan -> belum_konklusif", F.jalankan({"mode": "MODYAR"}, s2)["kesimpulan"] == "belum_konklusif")
    cek("saksi kosong tidak melempar", isinstance(F.jalankan({}, {}), dict))
    cek("describe menyebut jumlah uji + min jaringan",
        F.describe()["jumlah_uji"] == 10 and F.describe()["min_jaringan"] == 3)

    print()
    if FAIL:
        print("  [MERAH] verify_falsify: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_falsify: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
