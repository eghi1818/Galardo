"""Klien PostgreSQL minimal (wire protocol v3). Stdlib saja, fail-open.

Aktif hanya bila GALARDO_PG_DSN diisi. Auth didukung: trust, cleartext, md5,
scram-sha-256. Hanya simple query protocol (Q) - cukup untuk baca/tulis biasa.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import socket
import struct

DSN_ENV = "GALARDO_PG_DSN"
PROTO = 196608  # 3.0
STATS = {"connect": 0, "query": 0, "error": 0, "last_error": None}


def enabled():
    return bool((os.environ.get(DSN_ENV) or "").strip())


# ---------------- DSN ----------------
def parse_dsn(dsn):
    """postgres://user:pass@host:port/db -> dict. Toleran tanpa password/port."""
    s = (dsn or "").strip()
    for pre in ("postgres://", "postgresql://"):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    cred, sep, hostpart = s.rpartition("@")
    if not sep:
        cred, hostpart = "", s
    user, _, passwd = cred.partition(":")
    hostpart, _, dbname = hostpart.partition("/")
    host, _, port = hostpart.partition(":")
    return {"user": user or "postgres", "password": passwd,
            "host": host or "127.0.0.1", "port": int(port or 5432),
            "dbname": dbname or "postgres"}


# ---------------- framing ----------------
def pack(kind, payload):
    return kind + struct.pack(">I", len(payload) + 4) + payload


def startup(user, database, params=None):
    kv = {"user": user, "database": database}
    kv.update(params or {})
    body = struct.pack(">I", PROTO)
    for k, v in kv.items():
        body += k.encode() + b"\x00" + str(v).encode() + b"\x00"
    body += b"\x00"  # terminator daftar parameter (wajib oleh protokol)
    return struct.pack(">I", len(body) + 4) + body


def password_message(secret):
    return pack(b"p", secret.encode() + b"\x00")


def query_message(sql):
    return pack(b"Q", sql.encode() + b"\x00")


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("koneksi ditutup saat menunggu %d byte" % n)
        buf += chunk
    return buf


def read_message(sock):
    kind = recv_exact(sock, 1)
    (ln,) = struct.unpack(">I", recv_exact(sock, 4))
    payload = recv_exact(sock, ln - 4) if ln > 4 else b""
    return kind, payload


# ---------------- auth ----------------
def md5_password(secret, user, salt):
    inner = hashlib.md5((secret + user).encode()).hexdigest()
    return "md5" + hashlib.md5(inner.encode() + salt).hexdigest()


def scram_client_first(user, nonce):
    return "n,,n=%s,r=%s" % (user, nonce)


def scram_client_final(password, salt, iterations, auth_message, nonce, snonce):
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored = hashlib.sha256(client_key).digest()
    without_proof = "c=biws,r=%s%s" % (nonce, snonce)
    auth = (auth_message + "," + without_proof).encode()
    sig = hmac.new(stored, auth, hashlib.sha256).digest()
    proof = bytes(a ^ b for a, b in zip(client_key, sig))
    return "%s,p=%s" % (without_proof, base64.b64encode(proof).decode())


# ---------------- parsing ----------------
def parse_error(payload):
    out, i = {}, 0
    while i < len(payload):
        code = payload[i:i + 1].decode("latin-1")
        if code == "\x00":
            break
        j = payload.find(b"\x00", i + 1)
        if j < 0:
            break
        out[code] = payload[i + 1:j].decode("utf-8", "replace")
        i = j + 1
    return out


def parse_row_description(payload):
    (n,) = struct.unpack(">H", payload[:2])
    names, i = [], 2
    for _ in range(n):
        j = payload.find(b"\x00", i)
        names.append(payload[i:j].decode("utf-8", "replace"))
        i = j + 1 + 18  # oid4 attnum2 typoid4 typlen2 typmod4 format2
    return names


def parse_data_row(payload, ncols=None):
    (n,) = struct.unpack(">H", payload[:2])
    vals, i = [], 2
    for _ in range(n):
        (ln,) = struct.unpack(">i", payload[i:i + 4])
        i += 4
        if ln == -1:
            vals.append(None)
        else:
            vals.append(payload[i:i + ln].decode("utf-8", "replace"))
            i += ln
    return vals


# ---------------- koneksi ----------------
class PG(object):
    def __init__(self, sock, dsn):
        self.sock = sock
        self.dsn = dsn

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

    def query(self, sql):
        """(rows, error). rows = list dict. Tidak pernah melempar."""
        STATS["query"] += 1
        cols, rows, err = None, [], None
        try:
            self.sock.sendall(query_message(sql))
            while True:
                kind, payload = read_message(self.sock)
                if kind == b"T":
                    cols = parse_row_description(payload)
                elif kind == b"D":
                    rows.append(parse_data_row(payload))
                elif kind == b"E":
                    err = parse_error(payload)
                elif kind == b"Z":
                    break
        except Exception as exc:
            STATS["error"] += 1
            STATS["last_error"] = "%s: %s" % (type(exc).__name__, exc)
            return [], {"M": STATS["last_error"]}
        if err:
            STATS["error"] += 1
            STATS["last_error"] = err.get("M")
            return [], err
        if cols:
            return [dict(zip(cols, r)) for r in rows], None
        return [], None


def connect(dsn=None, timeout=6.0):
    d = parse_dsn(dsn or os.environ.get(DSN_ENV))
    sock = socket.create_connection((d["host"], d["port"]), timeout=timeout)
    sock.sendall(startup(d["user"], d["dbname"]))
    nonce = base64.b64encode(os.urandom(18)).decode()
    first = None
    while True:
        kind, payload = read_message(sock)
        if kind == b"R":
            (code,) = struct.unpack(">I", payload[:4])
            if code == 0:
                continue
            if code == 3:
                sock.sendall(password_message(d["password"]))
            elif code == 5:
                sock.sendall(password_message(md5_password(d["password"], d["user"], payload[4:8])))
            elif code == 10:
                first = scram_client_first(d["user"], nonce)
                body = b"SCRAM-SHA-256\x00" + struct.pack(">I", len(first)) + first.encode()
                sock.sendall(pack(b"p", body))
            elif code == 11:
                cont = payload[4:].decode("utf-8", "replace")
                parts = dict(p.split("=", 1) for p in cont.split(",") if "=" in p)
                final = scram_client_final(d["password"], base64.b64decode(parts["s"]),
                                           int(parts["i"]), first, nonce, parts["r"])
                sock.sendall(password_message(final))
            else:
                raise RuntimeError("metode auth tak didukung: %d" % code)
        elif kind == b"E":
            raise RuntimeError("auth gagal: %s" % parse_error(payload).get("M"))
        elif kind == b"Z":
            break
    STATS["connect"] += 1
    return PG(sock, d)


def stats():
    return dict(STATS)
