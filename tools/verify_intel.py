#!/usr/bin/env python3
"""Verifier BEHAVIORAL untuk backend/intel.py (ingest intel + pre-flight validasi).

Aturan: panggil fungsinya, cek efeknya (pelajaran #22). Tes jaringan punya jalur SKIP (#14).
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import intel as I  # noqa: E402

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


def cek_lempar(nama, fn, tipe=ValueError):
    try:
        fn()
    except tipe:
        cek(nama, True)
    except Exception as exc:
        cek(nama, False, "salah tipe: %r" % exc)
    else:
        cek(nama, False, "tidak melempar %s" % tipe.__name__)


def t_import_bersih():
    out = subprocess.run([sys.executable, "-c", "import intel"], cwd=BACKEND,
                         capture_output=True, text=True)
    cek("import intel tidak mencetak ke stdout",
        out.returncode == 0 and out.stdout.strip() == "",
        "rc=%s stdout=%r" % (out.returncode, out.stdout[:120]))


def t_parse_dict():
    it = I.parse({"domain": "PortalYogya.com.", "origin": "1.2.3.4", "waf": "Cloudflare"})
    cek("parse(dict): domain dinormalisasi", it["domain"] == "portalyogya.com", repr(it["domain"]))
    cek("parse(dict): alias origin -> origins", I.normalize_ip(it["origins"][0]) == "1.2.3.4", repr(it["origins"]))
    cek("parse(dict): waf terbaca", it["waf"] == "Cloudflare", repr(it["waf"]))


def t_parse_json():
    it = I.parse('{"host": "https://a.example.com:8443/x", "origins": "9.9.9.9, 8.8.8.8"}')
    cek("parse(JSON): host dibersihkan dari skema/port/path", it["domain"] == "a.example.com", repr(it["domain"]))
    cek("parse(JSON): daftar origin dipecah", len(it["origins"]) == 2, repr(it["origins"]))


def t_parse_teks():
    it = I.parse("domain: b.example.com\n- origin: 5.5.5.5\ncatatan: dari REA\nsumber: rea")
    cek("parse(teks): baris '-' dan 'key: value' terbaca", it["domain"] == "b.example.com", repr(it["domain"]))
    cek("parse(teks): notes + source terbaca", it["notes"] == "dari REA" and it["source"] == "rea", repr(it))


def t_parse_bytes():
    it = I.parse(b"domain=c.example.com\norigin=7.7.7.7")
    cek("parse(bytes): domain + origin terbaca", it["domain"] == "c.example.com" and it["origins"], repr(it))


def t_parse_asing():
    cek_lempar("parse(tipe asing) melempar ValueError", lambda: I.parse(12345))


def t_parse_kosong():
    it = I.parse(None)
    cek("parse(None) tidak crash, domain None", it["domain"] is None and it["origins"] == [], repr(it))


def t_normalize_host():
    cek("normalize_host: skema/port/titik/upper",
        I.normalize_host("  HTTPS://WWW.Example.COM:443/a?b=1.  ") == "www.example.com",
        repr(I.normalize_host("  HTTPS://WWW.Example.COM:443/a?b=1.  ")))


def t_normalize_ip():
    cek("normalize_ip: valid + kanonik", I.normalize_ip("001.002.003.004") == "1.2.3.4",
        repr(I.normalize_ip("001.002.003.004")))
    cek("normalize_ip: invalid -> None", I.normalize_ip("999.1.1.1") is None,
        repr(I.normalize_ip("999.1.1.1")))


def t_div_cocok():
    rows = I.divergences({"origins": ["1.2.3.4"], "waf": "cloudflare"},
                         {"origins": ["1.2.3.4"], "waf": "Cloudflare"})
    peta = {r["field"]: r["verdict"] for r in rows}
    cek("divergensi: klaim == ukur -> cocok", peta["origins"] == I.VERDICT_COCOK, repr(peta))


def t_div_beda():
    rows = I.divergences({"origins": ["1.2.3.4"]}, {"origins": ["9.9.9.9"]})
    baris = [r for r in rows if r["field"] == "origins"][0]
    cek("divergensi: beda terdeteksi", baris["verdict"] == I.VERDICT_BEDA, repr(baris))
    cek("divergensi: catatan menyebut arah beda",
        "diklaim tapi tak terlihat" in baris["catatan"] and "terukur tapi tak diklaim" in baris["catatan"],
        repr(baris["catatan"]))


def t_div_tak_terukur():
    rows = I.divergences({"origins": ["1.2.3.4"]}, {})
    baris = [r for r in rows if r["field"] == "origins"][0]
    cek("divergensi: klaim tanpa ukur -> tak terukur", baris["verdict"] == I.VERDICT_TAK_TERUKUR, repr(baris))


def t_div_tak_diklaim():
    rows = I.divergences({}, {"origins": ["1.2.3.4"]})
    baris = [r for r in rows if r["field"] == "origins"][0]
    cek("divergensi: ukur tanpa klaim -> tidak diklaim", baris["verdict"] == I.VERDICT_TAK_DIKLAIM, repr(baris))


def t_ringkasan_konsisten():
    rows = I.divergences({"origins": ["1.2.3.4"], "waf": "x"}, {"origins": ["9.9.9.9"], "waf": "x"})
    rk = I.ringkasan(rows)
    cek("ringkasan: total == jumlah baris", rk["total"] == len(rows), repr(rk))
    cek("ringkasan: selaras + tidak_selaras == total",
        rk["selaras"] + rk["tidak_selaras"] == rk["total"], repr(rk))
    cek("ringkasan: field dibanding lengkap", rk["total"] == len(I.FIELDS_DIBANDING), repr(rk))


def t_preflight_tanpa_ukur():
    pf = I.preflight({"domain": "x.example", "origin": "1.2.3.4"}, ukur=False)
    cek("preflight(ukur=False): pengukuran kosong", pf["pengukuran"] == {}, repr(pf["pengukuran"])[:120])
    cek("preflight: ringkasan konsisten dgn divergensi",
        pf["ringkasan"]["total"] == len(pf["divergensi"]), repr(pf["ringkasan"]))


def t_preflight_ukur_nyata():
    pf = I.preflight({"domain": "contoh.invalid", "origin": "1.2.3.4"}, ukur=True)
    cek("preflight(ukur=True): tidak crash + struktur lengkap",
        set(("divergensi", "ringkasan", "pengukuran", "catatan")).issubset(pf.keys()), repr(sorted(pf.keys())))


def t_errors():
    cek("errors(): domain kosong ditandai", I.errors({}) and "domain" in I.errors({})[0], repr(I.errors({})))
    cek("errors(): payload lengkap -> kosong", I.errors({"domain": "a.com", "origin": "1.1.1.1"}) == [],
        repr(I.errors({"domain": "a.com", "origin": "1.1.1.1"})))


def t_describe():
    d = I.describe()
    cek("describe(): menyebut field dibanding + prinsip hipotesis",
        set(I.FIELDS_DIBANDING).issubset(set(d["field_dibanding"])) and "hipotesis" in d["prinsip"],
        repr(d)[:160])


def t_ops_direktif():
    it = I.parse("domain: x.example\norigin: 1.2.3.4\nukur: 0")
    cek("ops: direktif ukur:0 terbaca dari teks", it["ops"].get("ukur") is False, repr(it.get("ops")))
    it2 = I.parse({"domain": "x.example", "ukur": 0})
    cek("ops: direktif ukur:0 terbaca dari dict", it2["ops"].get("ukur") is False, repr(it2.get("ops")))
    it3 = I.parse({"domain": "x.example"})
    cek("ops: tanpa direktif -> kosong (default ukur=1)", it3["ops"] == {}, repr(it3.get("ops")))


def t_preflight_hormati_ops():
    pf = I.preflight("domain: x.example\norigin: 1.2.3.4\nukur: 0")
    cek("preflight menghormati ukur:0 (tanpa jaringan)", pf["pengukuran"] == {}, repr(pf["pengukuran"])[:100])
    cek("preflight ukur:0 tetap penuh divergensi", len(pf["divergensi"]) == len(I.FIELDS_DIBANDING))


def main():
    print("== verify_intel (behavioral) ==")
    t_import_bersih()
    t_parse_dict()
    t_parse_json()
    t_parse_teks()
    t_parse_bytes()
    t_parse_asing()
    t_parse_kosong()
    t_normalize_host()
    t_normalize_ip()
    t_div_cocok()
    t_div_beda()
    t_div_tak_terukur()
    t_div_tak_diklaim()
    t_ringkasan_konsisten()
    t_preflight_tanpa_ukur()
    t_preflight_ukur_nyata()
    t_errors()
    t_ops_direktif()
    t_preflight_hormati_ops()
    t_describe()
    print()
    if FAIL:
        print("  [MERAH] verify_intel: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_intel: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
