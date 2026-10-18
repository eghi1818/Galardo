#!/usr/bin/env python3
"""Verifier P2: adapter provider proxy (parser toleran, fail-open, TTL, rotasi)."""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

import proxypool  # noqa: E402
import proxy_provider as pp  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  | " + str(detail)))


def bersih():
    pp._DAFTAR = []
    pp._IDX = 0
    pp._AT = 0.0
    pp._ERR = ""
    proxypool.clear()
    for k in (pp.URL_ENV, pp.KEY_ENV, pp.POOL_ENV, pp.TTL_ENV):
        os.environ.pop(k, None)


src = open(os.path.join(BACKEND, "proxy_provider.py")).read()

# A. bentuk sumber
check("A pakai netssl.context", "netssl" in src and "_ns.context()" in src)
check("A tidak melempar dari refresh", "except Exception" in src)
check("A env lengkap", all(k in src for k in (pp.URL_ENV, pp.KEY_ENV, pp.POOL_ENV, pp.TTL_ENV)))
check("A resolve() proxypool mengkonsultasi provider",
      "proxy_provider" in open(os.path.join(BACKEND, "proxypool.py")).read())

# B. parser toleran
bentuk = {
    "list dict host/port": json.dumps([{"host": "1.1.1.1", "port": 8000, "user": "u", "pass": "p"}]),
    "list dict ip/username": json.dumps([{"ip": "2.2.2.2", "port": 8001, "username": "u", "password": "p"}]),
    "bungkus data": json.dumps({"data": [{"host": "3.3.3.3", "port": 8002}]}),
    "bungkus proxies": json.dumps({"proxies": [{"ip": "4.4.4.4", "port": 8003}]}),
    "list string": json.dumps(["5.5.5.5:8004"]),
    "string user@host": json.dumps(["u:p@6.6.6.6:8005"]),
    "string host:port:user:pass": json.dumps(["7.7.7.7:8006:u:p"]),
    "teks baris": "8.8.8.8:8007\nu:p@9.9.9.9:8008\n",
}
harap = {"list dict host/port": 1, "list dict ip/username": 1, "bungkus data": 1,
         "bungkus proxies": 1, "list string": 1, "string user@host": 1,
         "string host:port:user:pass": 1, "teks baris": 2}
for nama, teks in bentuk.items():
    got = pp.parse_daftar(teks)
    check("B parser %s -> %d" % (nama, harap[nama]), len(got) == harap[nama], got)
check("B item user@host benar",
      pp.parse_daftar(json.dumps(["u:p@6.6.6.6:8005"]))[0] == ("6.6.6.6", 8005, "u", "p"),
      pp.parse_daftar(json.dumps(["u:p@6.6.6.6:8005"])))
check("B respons sampah -> list kosong", pp.parse_daftar("bukan apa-apa") == [], pp.parse_daftar("bukan apa-apa"))

# C. fail-open
bersih()
st = pp.status()
check("C tanpa URL -> configured False", st["configured"] is False, st)
check("C refresh tanpa URL tidak melempar", isinstance(pp.refresh(), dict))
check("C ensure tanpa URL -> False", pp.ensure("residential") is False)

# D. alur nyata dengan fetcher palsu
bersih()
os.environ[pp.URL_ENV] = "https://contoh.test/api/proxies"
os.environ[pp.POOL_ENV] = "residential"
os.environ[pp.TTL_ENV] = "60"
panggil = {"n": 0}


def fetcher():
    panggil["n"] += 1
    return json.dumps({"data": [{"host": "10.0.0.1", "port": 9001},
                                {"host": "10.0.0.2", "port": 9002}]})


st = pp.refresh(fetcher=fetcher)
check("D refresh mengisi daftar", st["count"] == 2, st)
check("D pool terdaftar di proxypool", proxypool.resolve("residential") == ("10.0.0.1", 9001),
      proxypool.resolve("residential"))
st = pp.refresh(fetcher=fetcher)
check("D TTL: fetch kedua tidak memanggil provider", panggil["n"] == 1, panggil)
st = pp.refresh(force=True, fetcher=fetcher)
check("D force memanggil provider lagi", panggil["n"] == 2, panggil)
st = pp.rotate()
check("D rotate pindah endpoint", st["endpoint"]["port"] == 9002, st["endpoint"])
check("D rotate mendaftarkan endpoint baru", proxypool.resolve("residential") == ("10.0.0.2", 9002),
      proxypool.resolve("residential"))
check("D rotate berputar kembali", pp.rotate()["endpoint"]["port"] == 9001)

# E. gagal fetch -> daftar lama dipertahankan
def fetcher_gagal():
    raise RuntimeError("403 dari provider")


st = pp.refresh(force=True, fetcher=fetcher_gagal)
check("E gagal -> daftar lama tetap ada", st["count"] == 2, st)
check("E error dilaporkan", "403" in st["error"], st["error"])
check("E resolve tetap jalan", proxypool.resolve("residential") is not None)

# F. env spec langsung (tanpa provider) tetap dipakai
bersih()
os.environ["GALARDO_PROXY_residential"] = "u:p@11.11.11.11:9999"
check("F env GALARDO_PROXY_<nama> menang", proxypool.resolve("residential") == ("11.11.11.11", 9999),
      proxypool.resolve("residential"))
bersih()

print("RESULTS: %d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)
