#!/usr/bin/env python3
"""Verifier behavioral backend/checkhost.py - inti parsing/agregasi diuji OFFLINE (fixture),
probe diuji dengan _get_json di-monkeypatch. Tanpa jaringan."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import checkhost as C  # noqa: E402

PASS = 0
FAIL = 0

NODES = {"ok": 1, "request_id": "rid-1", "nodes": {
    "us1.node.check-host.net": ["us", "New York"],
    "de1.node.check-host.net": ["de", "Frankfurt"],
    "sg1.node.check-host.net": ["sg", "Singapore"],
}}
HASIL_OK = {"us1.node.check-host.net": [[1, 0.12, "OK", "200"]],
            "de1.node.check-host.net": [[1, 0.34, "OK", "200"]],
            "sg1.node.check-host.net": [[1, 0.56, "OK", "200"]]}
HASIL_CAMPUR = {"us1.node.check-host.net": [[1, 0.12, "OK", "200"]],
                "de1.node.check-host.net": [[0, "timeout"]],
                "sg1.node.check-host.net": None}


def cek(nama, kondisi, detail=""):
    global PASS, FAIL
    if kondisi:
        PASS += 1
        print("  [ok]   %s" % nama)
    else:
        FAIL += 1
        print("  [GAGAL] %s  %s" % (nama, detail))


def t_import_bersih():
    out = subprocess.run([sys.executable, "-c", "import checkhost"], cwd=BACKEND,
                         capture_output=True, text=True)
    cek("import checkhost tidak mencetak ke stdout",
        out.returncode == 0 and out.stdout.strip() == "", repr(out.stdout[:120]))


def t_normalize():
    cek("normalize_url menambah skema", C.normalize_url("contoh.invalid") == "https://contoh.invalid")
    cek("normalize_url menjaga skema ada", C.normalize_url("http://a.b") == "http://a.b")
    cek("normalize_url kosong -> None", C.normalize_url("  ") is None)


def t_parse_nodes():
    n = C.parse_nodes(NODES)
    cek("parse_nodes: 3 node terbaca", len(n) == 3, repr(len(n)))
    cek("parse_nodes: kode negara tersimpan", n["de1.node.check-host.net"]["negara"] == "de", repr(n))
    cek("parse_nodes: payload kosong -> {}", C.parse_nodes({}) == {})


def t_parse_hasil():
    h = C.parse_hasil(HASIL_OK)
    cek("parse_hasil: sukses -> ok True + waktu", h["us1.node.check-host.net"]["ok"] is True and h["us1.node.check-host.net"]["waktu"] == 0.12, repr(h))
    hc = C.parse_hasil(HASIL_CAMPUR)
    cek("parse_hasil: gagal -> ok False + err", hc["de1.node.check-host.net"]["ok"] is False and "timeout" in hc["de1.node.check-host.net"]["err"], repr(hc))
    cek("parse_hasil: null -> belum siap", hc["sg1.node.check-host.net"]["ok"] is None, repr(hc))
    cek("parse_hasil: format aneh -> belum siap", C.parse_hasil({"x": "aneh"})["x"]["ok"] is None)


def t_grup():
    b = C.grup_negara(C.parse_nodes(NODES), C.parse_hasil(HASIL_CAMPUR))
    cek("grup_negara: satu baris per node", len(b) == 3, repr(len(b)))
    cek("grup_negara: terurut per negara", [x["negara"] for x in b] == sorted(x["negara"] for x in b), repr([x["negara"] for x in b]))
    cek("grup_negara: node tanpa hasil -> err jelas", any(x["err"] for x in b if x["ok"] is None))


def t_ringkas():
    b = C.grup_negara(C.parse_nodes(NODES), C.parse_hasil(HASIL_CAMPUR))
    r = C.ringkas(b)
    cek("ringkas: hitung ok/gagal/belum", (r["ok"], r["gagal"], r["belum"]) == (1, 1, 1), repr(r))
    cek("ringkas: negara dipecah", set(r["negara"]) == {"us", "de", "sg"}, repr(sorted(r["negara"])))
    cek("ringkas: verdict SEBAGIAN", "SEBAGIAN" in r["verdict"], repr(r["verdict"]))
    bmati = [{"negara": "us", "kota": "", "node": "n1", "ok": False, "waktu": None, "err": "t"},
             {"negara": "de", "kota": "", "node": "n2", "ok": False, "waktu": None, "err": "t"}]
    cek("ringkas: semua gagal -> MATI", C.ringkas(bmati)["verdict"].startswith("MATI"), repr(C.ringkas(bmati)["verdict"]))
    bhdp = [{"negara": "us", "kota": "", "node": "n1", "ok": True, "waktu": 0.1, "err": None}]
    cek("ringkas: semua sukses -> HIDUP", C.ringkas(bhdp)["verdict"].startswith("HIDUP"), repr(C.ringkas(bhdp)["verdict"]))
    cek("ringkas: tanpa baris -> tanpa node", C.ringkas([])["verdict"] == "tanpa node")


def t_tunggu_berhenti_di_batas():
    asli = C.ambil
    C.ambil = lambda rid, timeout=8.0: {"n1": {"ok": None, "waktu": None, "err": "belum siap"}}
    try:
        _, info = C.tunggu("rid-x", batas=0.5, jeda=0.2)
        cek("tunggu: berhenti di batas walau belum lengkap", info["lengkap"] is False and info["detik"] >= 0.4, repr(info))
    finally:
        C.ambil = asli


def t_probe_offline():
    asli = C._get_json
    def fake(path, timeout=8.0):
        return dict(NODES) if path.startswith("/check-http") else dict(HASIL_OK)
    C._get_json = fake
    try:
        h = C.probe("contoh.invalid", max_nodes=3, batas=2.0)
        cek("probe: struktur lengkap", set(("url", "nodes", "baris", "ringkasan", "catatan")).issubset(h.keys()), repr(sorted(h.keys())))
        cek("probe: url dinormalkan", h["url"] == "https://contoh.invalid", repr(h["url"]))
        cek("probe: verdict HIDUP terhitung", h["ringkasan"]["verdict"].startswith("HIDUP"), repr(h["ringkasan"]["verdict"]))
        cek("probe: catatan lengkap", h["catatan"] == "lengkap", repr(h["catatan"]))
    finally:
        C._get_json = asli


def t_probe_gagal_jaringan():
    asli = C._get_json
    def boom(path, timeout=8.0):
        raise OSError("jaringan mati")
    C._get_json = boom
    try:
        h = C.probe("contoh.invalid")
        cek("probe: gagal jaringan -> catatan, tidak crash", "gagal jaringan" in (h["catatan"] or ""), repr(h["catatan"]))
    finally:
        C._get_json = asli


def t_describe():
    d = C.describe()
    cek("describe(): menyebut sumber + prinsip", "check-host" in d["sumber"] and "negara" in d["prinsip"], repr(d)[:140])


def main():
    print("== verify_checkhost (offline, deterministik) ==")
    t_import_bersih(); t_normalize(); t_parse_nodes(); t_parse_hasil(); t_grup()
    t_ringkas(); t_tunggu_berhenti_di_batas(); t_probe_offline(); t_probe_gagal_jaringan(); t_describe()
    print()
    if FAIL:
        print("  [MERAH] verify_checkhost: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_checkhost: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
