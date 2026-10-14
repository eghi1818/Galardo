"""Raw DNS client built on the standard library only.

Galardo needs three things the stock ``socket`` module cannot give it:

* TXT lookups for the ``_galardo.<domain>`` ownership challenge,
* multi-resolver quorum so one lying or hijacked resolver cannot approve a
  target on its own,
* A/AAAA/CNAME lookups for origin discovery, including over a resolver we do
  not control (DoH) when UDP/53 is filtered.

Everything is dependency free: ``struct`` for the wire format, ``socket`` for
the transport, ``http.client`` for the DoH fallback.

Python 3.9 compatible: no PEP 604 unions, no ``match``.
"""

from __future__ import annotations

import http.client
import json
import random
import socket
import struct
import threading
import time
from urllib.parse import quote

__all__ = [
    "DNSError", "QTYPE", "DEFAULT_RESOLVERS", "DEFAULT_TIMEOUT", "resolve",
    "doh_resolve", "txt_quorum", "a_records", "aaaa_records", "cname_chain",
    "unquote_txt", "DNSClient",
]

DEFAULT_TIMEOUT = 4.0
DEFAULT_RESOLVERS = ("1.1.1.1", "8.8.8.8", "9.9.9.9")
DOH_ENDPOINTS = (
    ("dns.google", "/resolve"),
    ("cloudflare-dns.com", "/dns-query"),
)
USER_AGENT = "Galardo/1.0 (+dns)"

QTYPE = {
    "A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "PTR": 12, "MX": 15,
    "TXT": 16, "AAAA": 28, "SRV": 33, "CAA": 257,
}
QTYPE_REV = dict((value, key) for key, value in QTYPE.items())

CLASS_IN = 1
FLAG_RD = 0x0100
FLAG_TC = 0x0200
MAX_HOPS = 128

class DNSError(Exception):
    """Failure to obtain a usable answer from a resolver."""

def _qtype_code(qtype):
    if isinstance(qtype, int):
        return qtype
    try:
        return QTYPE[str(qtype).upper()]
    except KeyError:
        raise DNSError("unsupported qtype: %r" % (qtype,))

def _qtype_name(code):
    return QTYPE_REV.get(code, "TYPE%d" % code)

def encode_name(name):
    name = name.rstrip(".")
    out = bytearray()
    if name:
        for label in name.split("."):
            raw = label.encode("ascii", "replace")
            if len(raw) > 63:
                raise DNSError("label longer than 63 bytes: %s" % label)
            out.append(len(raw))
            out.extend(raw)
    out.append(0)
    return bytes(out)

def decode_name(buf, offset):
    labels = []
    returned = None
    hops = 0
    while True:
        if offset >= len(buf):
            raise DNSError("name runs past end of message")
        length = buf[offset]
        if length == 0:
            offset += 1
            if returned is None:
                returned = offset
            break
        if (length & 0xC0) == 0xC0:
            if offset + 1 >= len(buf):
                raise DNSError("truncated compression pointer")
            pointer = ((length & 0x3F) << 8) | buf[offset + 1]
            if returned is None:
                returned = offset + 2
            offset = pointer
            hops += 1
            if hops > MAX_HOPS:
                raise DNSError("compression pointer loop")
            continue
        offset += 1
        labels.append(buf[offset:offset + length].decode("latin-1"))
        offset += length
    return ".".join(labels), returned

def build_query(qname, qtype, qid, rd=True):
    header = struct.pack("!HHHHHH", qid, FLAG_RD if rd else 0, 1, 0, 0, 0)
    return header + encode_name(qname) + struct.pack("!HH", _qtype_code(qtype), CLASS_IN)

def parse_message(data):
    if len(data) < 12:
        raise DNSError("message shorter than a header")
    qid, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])
    offset = 12
    for _ in range(qdcount):
        _, offset = decode_name(data, offset)
        offset += 4
    records = []
    for _ in range(ancount):
        name, offset = decode_name(data, offset)
        if offset + 10 > len(data):
            raise DNSError("truncated resource record")
        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlength]
        records.append((name, rtype, ttl, rdata, offset))
        offset += rdlength
    return qid, flags & 0x000F, bool(flags & FLAG_TC), records

def _txt_value(rdata):
    parts = []
    index = 0
    while index < len(rdata):
        length = rdata[index]
        index += 1
        parts.append(rdata[index:index + length].decode("utf-8", "replace"))
        index += length
    return "".join(parts)

def _rdata_value(rtype, rdata, message, rdata_offset):
    if rtype == QTYPE["TXT"]:
        return _txt_value(rdata)
    if rtype == QTYPE["A"] and len(rdata) == 4:
        return socket.inet_ntoa(rdata)
    if rtype == QTYPE["AAAA"] and len(rdata) == 16:
        return socket.inet_ntop(socket.AF_INET6, rdata)
    if rtype in (QTYPE["CNAME"], QTYPE["NS"], QTYPE["PTR"]):
        return decode_name(message, rdata_offset)[0]
    if rtype == QTYPE["SOA"]:
        primary, cursor = decode_name(message, rdata_offset)
        mailbox, _ = decode_name(message, cursor)
        return "%s %s" % (primary, mailbox)
    if rtype == QTYPE["MX"] and len(rdata) >= 3:
        preference = struct.unpack("!H", rdata[:2])[0]
        exchange, _ = decode_name(message, rdata_offset + 2)
        return "%d %s" % (preference, exchange)
    if rtype == QTYPE["CAA"] and len(rdata) >= 2:
        flags = rdata[0]
        tag_length = rdata[1]
        tag = rdata[2:2 + tag_length].decode("ascii", "replace")
        value = rdata[2 + tag_length:].decode("utf-8", "replace")
        return "%d %s %s" % (flags, tag, value)
    return rdata.hex()

def _format_records(records, message, want=None):
    wanted = _qtype_code(want) if want else None
    out = []
    for name, rtype, ttl, rdata, rdata_offset in records:
        if wanted is not None and rtype != wanted:
            continue
        out.append({
            "name": name,
            "type": _qtype_name(rtype),
            "ttl": ttl,
            "value": _rdata_value(rtype, rdata, message, rdata_offset),
        })
    return out

def _recv_exact(sock, count):
    chunks = []
    remaining = count
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)

def _udp_query(payload, resolver, timeout, port):
    family = socket.AF_INET6 if ":" in resolver else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    try:
        sock.sendto(payload, (resolver, port))
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DNSError("udp query to %s timed out" % resolver)
            sock.settimeout(remaining)
            data, address = sock.recvfrom(65535)
            if address[0] == resolver:
                return data
    finally:
        sock.close()

def _tcp_query(payload, resolver, timeout, port):
    family = socket.AF_INET6 if ":" in resolver else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        sock.connect((resolver, port))
        sock.sendall(struct.pack("!H", len(payload)) + payload)
        header = _recv_exact(sock, 2)
        if len(header) != 2:
            raise DNSError("tcp connection closed before length prefix")
        length = struct.unpack("!H", header)[0]
        body = _recv_exact(sock, length)
        if len(body) != length:
            raise DNSError("tcp short read: %d of %d" % (len(body), length))
        return body
    finally:
        sock.close()

def resolve(qname, qtype="A", resolver="1.1.1.1", timeout=DEFAULT_TIMEOUT, port=53, tcp=False):
    """Query one resolver. Returns ``(rcode, records)``.

    A truncated UDP answer is transparently retried over TCP.
    """
    qid = random.randint(0, 0xFFFF)
    payload = build_query(qname, qtype, qid)
    if tcp:
        data = _tcp_query(payload, resolver, timeout, port)
    else:
        data = _udp_query(payload, resolver, timeout, port)
    rid, rcode, truncated, records = parse_message(data)
    if rid != qid:
        raise DNSError("transaction id mismatch from %s" % resolver)
    if truncated and not tcp:
        return resolve(qname, qtype, resolver, timeout, port, tcp=True)
    return rcode, _format_records(records, data, qtype)

def unquote_txt(value):
    value = str(value).strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value.replace('\\"', '"').replace("\\\\", "\\")

def doh_resolve(qname, qtype="A", timeout=DEFAULT_TIMEOUT, endpoints=None):
    """Resolve over HTTPS when UDP/53 is filtered. Raises if every endpoint fails."""
    endpoints = endpoints or DOH_ENDPOINTS
    last_error = None
    for host, path in endpoints:
        conn = None
        try:
            conn = http.client.HTTPSConnection(host, timeout=timeout)
            url = "%s?name=%s&type=%s" % (path, quote(qname), quote(str(qtype)))
            if host == "cloudflare-dns.com":
                url += "&ct=application/dns-json"
            conn.request("GET", url, headers={
                "accept": "application/dns-json",
                "user-agent": USER_AGENT,
            })
            response = conn.getresponse()
            body = response.read()
            if response.status != 200:
                last_error = DNSError("doh %s returned %d" % (host, response.status))
                continue
            document = json.loads(body.decode("utf-8"))
            records = []
            for answer in document.get("Answer") or []:
                records.append({
                    "name": str(answer.get("name", qname)).rstrip("."),
                    "type": _qtype_name(int(answer.get("type", 0))),
                    "ttl": int(answer.get("TTL", 0)),
                    "value": unquote_txt(answer.get("data", "")),
                })
            return records
        except Exception as exc:
            last_error = exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    raise DNSError("all DoH endpoints failed: %r" % (last_error,))

def txt_quorum(qname, token, resolvers=None, required=2, timeout=DEFAULT_TIMEOUT,
               allow_doh=True, port=53):
    """Return ``(ok, evidence)``.

    ``ok`` is True only when at least ``required`` resolvers independently
    returned a TXT record containing ``token``. One resolver is never enough.
    """
    resolvers = list(resolvers or DEFAULT_RESOLVERS)
    evidence = {}
    for resolver in resolvers:
        entry = {"ok": False}
        try:
            rcode, records = resolve(qname, "TXT", resolver, timeout, port)
            entry["rcode"] = rcode
            matched = [r["value"] for r in records if token in r["value"]]
            if matched:
                entry["ok"] = True
                entry["matched"] = matched
            elif allow_doh:
                try:
                    doh = doh_resolve(qname, "TXT", timeout)
                    matched = [r["value"] for r in doh if token in r["value"]]
                    if matched:
                        entry["ok"] = True
                        entry["via"] = "doh"
                        entry["matched"] = matched
                except Exception as exc:
                    entry["doh_error"] = str(exc)
        except Exception as exc:
            entry["error"] = str(exc)
        evidence[resolver] = entry
    ok_count = sum(1 for entry in evidence.values() if entry.get("ok"))
    return ok_count >= required, {
        "qname": qname,
        "token": token,
        "required": required,
        "ok_count": ok_count,
        "resolvers": evidence,
    }

def _records_for(qname, qtype, resolver, timeout):
    rcode, records = resolve(qname, qtype, resolver, timeout)
    if rcode != 0:
        raise DNSError("rcode %d for %s %s" % (rcode, qname, qtype))
    return records

def a_records(qname, resolver="1.1.1.1", timeout=DEFAULT_TIMEOUT):
    return [r["value"] for r in _records_for(qname, "A", resolver, timeout)]

def aaaa_records(qname, resolver="1.1.1.1", timeout=DEFAULT_TIMEOUT):
    return [r["value"] for r in _records_for(qname, "AAAA", resolver, timeout)]

def cname_chain(qname, resolver="1.1.1.1", timeout=DEFAULT_TIMEOUT, limit=16):
    chain = []
    current = qname
    for _ in range(limit):
        records = _records_for(current, "CNAME", resolver, timeout)
        if not records:
            break
        target = records[0]["value"].rstrip(".")
        if target in chain:
            break
        chain.append(target)
        current = target
    return chain

class DNSClient(object):
    """Resolver set plus a small positive/negative cache."""

    def __init__(self, resolvers=None, timeout=DEFAULT_TIMEOUT, port=53,
                 allow_doh=True, cache_ttl=60.0, negative_ttl=10.0):
        self.resolvers = list(resolvers or DEFAULT_RESOLVERS)
        self.timeout = timeout
        self.port = port
        self.allow_doh = allow_doh
        self.cache_ttl = cache_ttl
        self.negative_ttl = negative_ttl
        self._cache = {}
        self._lock = threading.Lock()

    def _cached(self, key):
        with self._lock:
            entry = self._cache.get(key)
        if not entry:
            return None
        expires, payload = entry
        if expires < time.monotonic():
            with self._lock:
                self._cache.pop(key, None)
            return None
        return payload

    def _store(self, key, payload, ok):
        ttl = self.cache_ttl if ok else self.negative_ttl
        with self._lock:
            self._cache[key] = (time.monotonic() + ttl, payload)

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

    def query(self, qname, qtype="A", resolver=None):
        resolver = resolver or self.resolvers[0]
        key = (qname.lower(), str(qtype).upper(), resolver)
        cached = self._cached(key)
        if cached is not None:
            return cached
        result = resolve(qname, qtype, resolver, self.timeout, self.port)
        self._store(key, result, result[0] == 0)
        return result

    def txt(self, qname, resolver=None):
        return self.query(qname, "TXT", resolver)

    def a(self, qname, resolver=None):
        return self.query(qname, "A", resolver)

    def quorum_txt(self, qname, token, required=2):
        return txt_quorum(qname, token, self.resolvers, required,
                          self.timeout, self.allow_doh, self.port)
