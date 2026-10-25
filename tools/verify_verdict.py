#!/usr/bin/env python3
"""Verifier behavioral verdict.py - fixture per mode + anti-pola. Offline."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import verdict as V  # noqa: E402

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


def vantage(n=3, ok=False, jaringan=("rumahan", "seluler", "vps")):
    return [{"jaringan": jaringan[i % len(jaringan)], "asn": "AS%d" % (i + 1), "ok": ok} for i in range(n)]


def dasar():
    return {"domain": "contoh.test", "vantage": vantage(3, True),
            "dns": {"ok": True, "nxdomain": False}, "tcp": {"ok": True, "ms": 25},
            "tls": {"ok": True}, "http": {"ok": True, "status": 200}}


def main():
    print("== verify_verdict (offline) ==")
    out = subprocess.run([sys.executable, "-c", "import verdict"], cwd=BACKEND, capture_output=True, text=True)
    cek("import verdict tidak mencetak ke stdout", out.returncode == 0 and out.stdout.strip() == "", repr(out.stdout[:100]))

    for m in ("DNS_MATI", "NET_MATI", "TLS_MATI", "EDGE_MATI", "ORIGIN_MATI", "APP_MATI",
              "KONTEN_HILANG", "SOFT_404", "MODYAR", "MATI_OVERRIDE", "HIDUP"):
        cek("mode %s terdaftar" % m, m in V.MODES)

    b = dasar()
    cek("sehat -> HIDUP", V.klasifikasi(b)[0] == "HIDUP", V.klasifikasi(b)[0])

    b = dasar(); b["http"] = {"ok": False, "status": 500, "fingerprint": "akamai_error"}
    cek("halaman errors.edgesuite.net -> EDGE_MATI", V.klasifikasi(b)[0] == "EDGE_MATI", V.klasifikasi(b)[0])

    b = dasar(); b["http"] = {"ok": False, "status": 522}
    cek("522 -> ORIGIN_MATI", V.klasifikasi(b)[0] == "ORIGIN_MATI", V.klasifikasi(b)[0])

    b = dasar(); b["http"] = {"ok": False, "status": 503, "fingerprint": "brand"}
    cek("503 halaman brand -> APP_MATI", V.klasifikasi(b)[0] == "APP_MATI", V.klasifikasi(b)[0])

    b = dasar(); b["http"] = {"ok": True, "status": 410}
    cek("410 -> KONTEN_HILANG", V.klasifikasi(b)[0] == "KONTEN_HILANG", V.klasifikasi(b)[0])
    cek("410 -> niat disengaja", V.niat(b, "KONTEN_HILANG").startswith("disengaja"), V.niat(b, "KONTEN_HILANG"))

    b = dasar(); b["http"] = {"ok": True, "status": 200, "kemiripan_parkir": 0.93}
    cek("200 tapi parkir -> SOFT_404", V.klasifikasi(b)[0] == "SOFT_404", V.klasifikasi(b)[0])

    b = dasar(); b["dns"] = {"ok": False, "nxdomain": True}
    cek("NXDOMAIN -> DNS_MATI", V.klasifikasi(b)[0] == "DNS_MATI", V.klasifikasi(b)[0])

    b = dasar(); b["tcp"] = {"ok": False}
    cek("TCP gagal -> NET_MATI", V.klasifikasi(b)[0] == "NET_MATI", V.klasifikasi(b)[0])

    b = dasar(); b["tls"] = {"ok": False}
    cek("TLS gagal -> TLS_MATI", V.klasifikasi(b)[0] == "TLS_MATI", V.klasifikasi(b)[0])

    b = {"domain": "mati.test", "vantage": vantage(3, False),
         "dns": {"ok": False}, "tcp": {"ok": False}, "tls": {"ok": False}, "http": {"ok": False}}
    cek("semua lapisan gagal -> MODYAR", V.klasifikasi(b)[0] == "MODYAR", V.klasifikasi(b)[0])

    b = dasar(); b["override"] = {"aktif": True, "oleh": "galardo"}
    cek("override aktif -> MATI_OVERRIDE", V.klasifikasi(b)[0] == "MATI_OVERRIDE", V.klasifikasi(b)[0])
    cek("MATI_OVERRIDE -> niat 'kita'", V.niat(b, "MATI_OVERRIDE") == "kita", V.niat(b, "MATI_OVERRIDE"))

    b = dasar(); b["vantage"] = vantage(1, False)
    v = V.verdict(b, "KJ-1")
    cek("1 saksi -> belum_konklusif", v["belum_konklusif"] is True and v["keyakinan"] == "belum_konklusif", repr(v["keyakinan"]))
    b = dasar(); b["vantage"] = vantage(3, False)
    cek("3 jaringan konsisten -> keyakinan tinggi", V.verdict(b)["keyakinan"] == "tinggi", repr(V.verdict(b)["keyakinan"]))

    b = dasar(); b["tls"] = {"ok": False}
    cek("kontradiksi DNS/TCP ok + TLS gagal DILAPORKAN", any("konfigurasi rusak" in k for k in V.kontradiksi(b)), repr(V.kontradiksi(b)))

    b = dasar(); b["http"] = {"ok": True, "status": 404}
    cek("anti-pola: 404 bukan MODYAR", V.verdict(b)["mode"] == "KONTEN_HILANG", V.verdict(b)["mode"])

    cek("falsifikasi menyediakan 9 uji", len(V.falsifikasi(dasar())) == 9, repr(len(V.falsifikasi(dasar()))))
    cek("describe menyebut 5 aturan", len(V.describe()["aturan"]) == 5, repr(V.describe()["aturan"]))
    v = V.verdict(dasar(), "KJ-2")
    for k in ("kejadian", "domain", "mode", "lapisan", "niat", "keyakinan", "kontradiksi", "falsifikasi"):
        cek("verdict punya kunci %s" % k, k in v)

    print()
    if FAIL:
        print("  [MERAH] verify_verdict: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_verdict: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
