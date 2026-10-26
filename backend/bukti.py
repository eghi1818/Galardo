"""Galardo - ledger bukti ber-hash (hash chain).

Setiap entri menyimpan SHA-256 tiap artefak + hash entri yang merangkai hash entri sebelumnya.
Ubah satu entri -> rantai putus. Bukti jadi tidak bisa diubah diam-diam.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

GENESIS = "0" * 64

__all__ = ["GENESIS", "sha256_bytes", "sha256_teks", "sha256_file", "buat", "simpan",
           "muat", "verifikasi_rantai", "ringkas", "describe"]


def sha256_bytes(b):
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def sha256_teks(s):
    return sha256_bytes(str(s))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blok in iter(lambda: fh.read(65536), b""):
            h.update(blok)
    return h.hexdigest()


def _kanonik(d):
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def buat(kejadian, artefak=None, sebelumnya=GENESIS, waktu=None):
    """artefak: {nama: bytes|str|{'file': path}} - hanya HASH yang disimpan."""
    art = {}
    for nama, nilai in (artefak or {}).items():
        if isinstance(nilai, dict) and nilai.get("file"):
            art[str(nama)] = sha256_file(nilai["file"])
        elif isinstance(nilai, (bytes, bytearray, str)):
            art[str(nama)] = sha256_bytes(nilai)
        else:
            art[str(nama)] = sha256_teks(nilai)
    isi = {"kejadian": str(kejadian), "waktu": waktu or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "sebelumnya": sebelumnya, "artefak": art}
    isi["hash_entri"] = sha256_teks(_kanonik(isi))
    return isi


def simpan(entri, path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(_kanonik(entri) + "\n")
    with open(path + ".sha256", "w", encoding="utf-8") as fh:
        fh.write(sha256_file(path) + "  " + os.path.basename(path) + "\n")
    return path


def muat(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(b) for b in fh if b.strip()]


def verifikasi_rantai(entri_list):
    prev = GENESIS
    for i, e in enumerate(entri_list):
        if e.get("sebelumnya") != prev:
            return {"ok": False, "rusak_pada": i, "alasan": "tautan sebelumnya tidak cocok"}
        isi = {k: e.get(k) for k in ("kejadian", "waktu", "sebelumnya", "artefak")}
        if sha256_teks(_kanonik(isi)) != e.get("hash_entri"):
            return {"ok": False, "rusak_pada": i, "alasan": "hash entri tidak cocok"}
        prev = e["hash_entri"]
    return {"ok": True, "rusak_pada": None, "jumlah": len(entri_list)}


def ringkas(entri_list):
    return {"jumlah": len(entri_list),
            "kejadian": sorted({e.get("kejadian") for e in entri_list}),
            "kepala": entri_list[-1]["hash_entri"] if entri_list else GENESIS}


def describe():
    return {"prinsip": "hash chain: ubah 1 entri -> rantai putus", "genesis": GENESIS}
