#!/usr/bin/env python3
"""Verifier behavioral ledger bukti (hash chain)."""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import bukti as E  # noqa: E402

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


def main():
    print("== verify_evidence (offline) ==")
    out = subprocess.run([sys.executable, "-c", "import bukti"], cwd=BACKEND, capture_output=True, text=True)
    cek("import bukti tanpa cetak stdout", out.returncode == 0 and out.stdout.strip() == "", repr(out.stdout[:100]))

    cek("sha256 deterministik", E.sha256_teks("a") == E.sha256_teks("a") and E.sha256_teks("a") != E.sha256_teks("b"))
    e1 = E.buat("kejadian-1", {"body": "halo"})
    cek("entri punya hash_entri 64 hex", isinstance(e1["hash_entri"], str) and len(e1["hash_entri"]) == 64)
    cek("artefak disimpan sebagai hash", len(e1["artefak"]["body"]) == 64)
    e1b = E.buat("kejadian-1", {"body": "halo"}, waktu=e1["waktu"])
    cek("hash entri deterministik", e1b["hash_entri"] == e1["hash_entri"])
    e2 = E.buat("kejadian-2", {"body": "halo"}, sebelumnya=e1["hash_entri"])
    cek("entri berikut merangkai hash sebelumnya", e2["sebelumnya"] == e1["hash_entri"] and e2["hash_entri"] != e1["hash_entri"])

    tmp = tempfile.mkdtemp(prefix="galardo-bukti-")
    path = os.path.join(tmp, "ledger.jsonl")
    E.simpan(e1, path); E.simpan(e2, path)
    cek("ledger tersimpan (2 baris)", len(E.muat(path)) == 2)
    cek("file .sha256 dibuat", os.path.exists(path + ".sha256"))
    cek("rantai utuh terverifikasi", E.verifikasi_rantai(E.muat(path))["ok"] is True)

    rusak = E.muat(path)
    rusak[1]["kejadian"] = "diubah"
    v = E.verifikasi_rantai(rusak)
    cek("perubahan entri TERDETEKSI", v["ok"] is False and v["rusak_pada"] == 1, repr(v))

    putus = E.muat(path)
    putus[1]["sebelumnya"] = "0" * 64
    cek("tautan rantai putus TERDETEKSI", E.verifikasi_rantai(putus)["ok"] is False)
    cek("ringkas: jumlah + kepala", E.ringkas(E.muat(path))["jumlah"] == 2 and len(E.ringkas(E.muat(path))["kepala"]) == 64)
    cek("describe menyebut prinsip rantai", "rantai" in E.describe()["prinsip"] or "chain" in E.describe()["prinsip"])

    print()
    if FAIL:
        print("  [MERAH] verify_evidence: %d hijau, %d GAGAL" % (PASS, FAIL))
        return 1
    print("  [ok]   verify_evidence: %d cek hijau" % PASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
