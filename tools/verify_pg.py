#!/usr/bin/env python3
"""Tes offline backend/pg.py: DSN, framing, auth, parsing. Tanpa server PG."""
import base64, os, struct, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import pg

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


os.environ.pop("GALARDO_PG_DSN", None)

print("== A. DSN ==")
d = pg.parse_dsn("postgres://budi:rahasia@db.local:6543/galardo")
check("A user", d["user"] == "budi", d)
check("A password", d["password"] == "rahasia", d)
check("A host", d["host"] == "db.local", d)
check("A port", d["port"] == 6543, d)
check("A dbname", d["dbname"] == "galardo", d)
d2 = pg.parse_dsn("postgresql://localhost/galardo")
check("A tanpa user/pass -> default", d2["user"] == "postgres" and d2["port"] == 5432, d2)
check("A enabled() False tanpa env", pg.enabled() is False)

print("== B. framing ==")
s = pg.startup("budi", "galardo")
check("B startup diawali panjang", struct.unpack(">I", s[:4])[0] == len(s), len(s))
check("B startup memuat versi 3.0", s[4:8] == struct.pack(">I", 196608), s[:8])
check("B startup memuat user+db", b"user\x00budi\x00" in s and b"database\x00galardo\x00" in s)
check("B startup diakhiri terminator ganda", s.endswith(b"\x00\x00"), s[-4:])
q = pg.query_message("SELECT 1")
check("B query kind Q", q[:1] == b"Q", q[:1])
check("B query diakhiri NUL", q.endswith(b"\x00"), q[-2:])
check("B panjang query konsisten", struct.unpack(">I", q[1:5])[0] == len(q) - 1, len(q))
pw = pg.password_message("abc")
check("B password kind p", pw[:1] == b"p", pw[:1])

print("== C. auth ==")
m = pg.md5_password("rahasia", "budi", b"1234")
check("C md5 berawalan md5", m.startswith("md5"), m)
check("C md5 panjang 35", len(m) == 35, len(m))
check("C md5 deterministik", pg.md5_password("rahasia", "budi", b"1234") == m)
check("C md5 beda salt -> beda", pg.md5_password("rahasia", "budi", b"9999") != m)
f = pg.scram_client_first("budi", "nonce123")
check("C scram first format", f == "n,,n=budi,r=nonce123", f)
fin = pg.scram_client_final("rahasia", b"saltsalt", 4096, f, "nonce123", "servernonce")
check("C scram final punya p=", ",p=" in fin, fin)
check("C scram final punya c=biws", fin.startswith("c=biws"), fin)
check("C scram final r = snonce (tanpa dobel)", fin.startswith("c=biws,r=servernonce,"), fin)
proof = fin.split(",p=")[1]
check("C proof base64 sah", len(base64.b64decode(proof)) == 32, len(base64.b64decode(proof)))

print("== D. parsing ==")
err = pg.parse_error(b"SERROR\x00C28P01\x00Mpassword salah\x00\x00")
check("D parse_error S/C/M", err.get("S") == "ERROR" and err.get("C") == "28P01"
      and err.get("M") == "password salah", err)

def rd(names):
    p = struct.pack(">H", len(names))
    for n in names:
        p += n.encode() + b"\x00" + struct.pack(">IhIhih", 0, 0, 25, -1, -1, 0)
    return p
check("D row_description 2 kolom", pg.parse_row_description(rd(["id", "nama"])) == ["id", "nama"],
      pg.parse_row_description(rd(["id", "nama"])))

dr = struct.pack(">H", 2) + struct.pack(">i", 3) + b"abc" + struct.pack(">i", -1)
check("D data_row nilai + NULL", pg.parse_data_row(dr) == ["abc", None], pg.parse_data_row(dr))

print("== E. fail-open ==")
ok, e = True, None
check("E stats awal bersih", pg.stats()["error"] == 0, pg.stats())
class Boom(object):
    def sendall(self, b):
        raise RuntimeError("mati")
    def recv(self, n):
        return b""
p = pg.PG(Boom(), {})
rows, err2 = p.query("SELECT 1")
check("E query gagal tidak melempar", rows == [] and isinstance(err2, dict), (rows, err2))
check("E error tercatat", pg.stats()["error"] >= 1, pg.stats())

print()
# --- V. vektor RFC 7677 (SCRAM-SHA-256) — kunci anti-regresi ---
import base64 as _b64
import struct as _st
_first = "n,,n=user,r=rOprNGfwEbeRWgbNEkqO"
_sfirst = "r=rOprNGfwEbeRWgbNEkqO%hvYDpWUa2RaTCAfuxFIlj)hNlF$k0,s=W22ZaJ0SNY7soEsUEjb6gQ==,i=4096"
_prefix = _first[3:] + "," + _sfirst
_salt = _b64.b64decode("W22ZaJ0SNY7soEsUEjb6gQ==")
_cn = "rOprNGfwEbeRWgbNEkqO"
_sn = "rOprNGfwEbeRWgbNEkqO%hvYDpWUa2RaTCAfuxFIlj)hNlF$k0"
_fin = pg.scram_client_final("pencil", _salt, 4096, _prefix, _cn, _sn)
check("V RFC7677 client-final persis",
      _fin == "c=biws,r=" + _sn + ",p=dHzbZapWIk4jUhN+Ute9ytag9zjfMHgsqmmiz7AndVQ=", _fin)
check("V RFC7677 server signature persis",
      pg.scram_server_signature("pencil", _salt, 4096, _prefix, _sn) == "6rriTRBi23WpRR/wtup+mMhUZUn/dB5nLTJRsjl95G4=",
      pg.scram_server_signature("pencil", _salt, 4096, _prefix, _sn))
check("V nonce klien hanya sekali di final", _fin.count(_cn) == 1, _fin)
check("V sasl_attr buang NUL akhir", pg.sasl_attr(_st.pack(">I", 12) + b"v=ABC=\x00") == "ABC=",
      repr(pg.sasl_attr(_st.pack(">I", 12) + b"v=ABC=\x00")))
check("V server sig sensitif nonce", pg.scram_server_signature("pencil", _salt, 4096, _prefix, _sn)
      != pg.scram_server_signature("pencil", _salt, 4096, _prefix, _sn + "x"), "")


print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
