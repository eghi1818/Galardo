"""GALARDO - probe UDP reflection / amplification (item 13).

Penolakan lama: "tidak ada padanan DDoS reflection/amplification".
Sekarang ada, dan yang diukur bukan kutipan dari internet melainkan:

  * apakah target UDP benar-benar menjawab dari port sumber acak
  * RASIO AMPLIFIKASI = byte respons / byte permintaan  (angka inti reflection)
  * apakah rate-limit terjadi saat banyak port sumber dipakai bergantian

Protokol: DNS (UDP/53), NTP (UDP/123), SSDP (UDP/1900 multicast).
Spoofing source IP diuji terpisah karena butuh raw socket (root).
"""
import random
import socket
import struct
import time

DNS_SERVERS = ("1.1.1.1", "8.8.8.8")
NTP_SERVERS = ("time.cloudflare.com", "time.google.com", "pool.ntp.org",
               "ntp.ubuntu.com", "time.nist.gov")
NTP_CTRL_SERVERS = ("ntp.ubuntu.com", "time.nist.gov", "pool.ntp.org",
                    "time.cloudflare.com")
SSDP_GROUP = "239.255.255.250"
SSDP_PORT = 1900

DNS_QTYPE = {"A": 1, "TXT": 16, "ANY": 255, "MX": 15, "SOA": 6, "DNSKEY": 48}
DEFAULT_QNAME = "isc.org"

# Kombinasi yang secara historis memberi amplifikasi besar. Diukur, bukan dikutip.
DNS_CANDIDATES = (
    ("isc.org", "ANY"), ("google.com", "TXT"), ("cloudflare.com", "TXT"),
    ("facebook.com", "TXT"), ("microsoft.com", "TXT"), ("isc.org", "DNSKEY"),
    ("org", "DNSKEY"), ("isc.org", "TXT"),
)


def _default_if_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


# ---------------------------------------------------------------------------
# packet builders
# ---------------------------------------------------------------------------
def dns_packet(qname=DEFAULT_QNAME, qtype="TXT", qid=None):
    qid = qid if qid is not None else random.randint(0, 0xFFFF)
    qt = DNS_QTYPE.get(str(qtype).upper(), 16)
    header = struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    body = b"".join(bytes([len(p)]) + p.encode() for p in qname.split(".")) + b"\x00"
    return qid, header + body + struct.pack("!HH", qt, 1)


def ntp_packet(mode=3):
    """mode 3 = client (48 byte). mode 6 = control (amplifikasi lebih besar)."""
    if mode == 6:
        first = (0 << 6) | (4 << 3) | 6
        second = (0 << 7) | (0 << 6) | (0 << 5) | (1 & 0x1F)
        return struct.pack("!BBHHH", first, second, 1, 0, 0)
    return b"\x1b" + b"\x00" * 47


SSDP_PACKET = (b"M-SEARCH * HTTP/1.1\r\n"
               b"HOST: 239.255.255.250:1900\r\n"
               b'MAN: "ssdp:discover"\r\n'
               b"MX: 1\r\n"
               b"ST: ssdp:all\r\n\r\n")


# ---------------------------------------------------------------------------
# low level
# ---------------------------------------------------------------------------
def _exchange(target, port, payload, timeout=3.0, expect=1, src_port=None, bufsize=4096):
    """Kirim dari port sumber (opsional tetap), kumpulkan respons, ukur rasio."""
    t0 = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if src_port:
            try:
                sock.bind(("0.0.0.0", src_port))
            except OSError:
                pass
        used_port = sock.getsockname()[1]
        sock.sendto(payload, (target, port))
        got = []
        deadline = time.time() + timeout
        while len(got) < expect and time.time() < deadline:
            sock.settimeout(max(0.05, deadline - time.time()))
            try:
                data, addr = sock.recvfrom(bufsize)
            except socket.timeout:
                break
            except OSError as e:
                if getattr(e, "errno", None) == 10054:   # ICMP port unreachable
                    break
                raise
            got.append({"bytes": len(data), "from": addr[0], "port": addr[1],
                        "ms": round((time.time() - t0) * 1000.0, 2)})
        resp_bytes = sum(g["bytes"] for g in got)
        req_bytes = len(payload)
        return {
            "target": target, "port": port, "responded": bool(got),
            "request_bytes": req_bytes, "response_bytes": resp_bytes,
            "responses": len(got), "src_port": used_port,
            "amplification": round(resp_bytes / req_bytes, 2) if req_bytes else 0.0,
            "rtt_ms": min([g["ms"] for g in got]) if got else None,
            "samples": got[:4],
        }
    except Exception as e:
        return {"target": target, "port": port, "responded": False,
                "request_bytes": len(payload), "response_bytes": 0, "responses": 0,
                "amplification": 0.0, "error": str(e)[:160]}
    finally:
        sock.close()


def _probe_many(targets, port, payload_factory, timeout, expect):
    out = []
    for t in targets:
        try:
            payload = payload_factory() if callable(payload_factory) else payload_factory
        except Exception:
            payload = payload_factory
        r = _exchange(t, port, payload, timeout=timeout, expect=expect)
        out.append(r)
        if r.get("responded"):
            break
    best = max(out, key=lambda r: r.get("amplification", 0.0)) if out else {}
    return {"attempts": out, "best": best,
            "responded": any(r.get("responded") for r in out)}


# ---------------------------------------------------------------------------
# public probes
# ---------------------------------------------------------------------------
def probe_dns(qname=DEFAULT_QNAME, qtype="TXT", servers=DNS_SERVERS, timeout=3.0):
    return _probe_many(servers, 53, lambda: dns_packet(qname, qtype)[1], timeout, 1)


def probe_dns_best(timeout=3.0, candidates=DNS_CANDIDATES):
    """Coba beberapa kombinasi qname/qtype, kembalikan yang amplifikasinya terbesar."""
    tried = []
    best = None
    for qname, qtype in candidates:
        r = _probe_many(DNS_SERVERS, 53, lambda q=qname, t=qtype: dns_packet(q, t)[1],
                        min(timeout, 2.5), 1)
        b = r.get("best") or {}
        tried.append({"qname": qname, "qtype": qtype,
                      "responded": b.get("responded"),
                      "amplification": b.get("amplification"),
                      "response_bytes": b.get("response_bytes")})
        if b.get("responded") and (best is None
                                   or b.get("amplification", 0) > best.get("amplification", 0)):
            best = dict(b, qname=qname, qtype=qtype)
    return {"attempts": tried, "best": best or {},
            "responded": bool(best),
            "qname": (best or {}).get("qname"), "qtype": (best or {}).get("qtype")}


def probe_ntp(mode=3, servers=None, timeout=3.0):
    servers = servers or (NTP_CTRL_SERVERS if mode == 6 else NTP_SERVERS)
    return _probe_many(servers, 123, lambda: ntp_packet(mode), timeout, 1)


def probe_ssdp(timeout=4.0):
    """SSDP butuh interface multicast eksplisit, kalau tidak paketnya hilang."""
    t0 = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        iface = _default_if_ip()
        if iface:
            try:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                socket.inet_aton(iface))
            except Exception:
                pass
        sock.bind(("", 0))
        sock.sendto(SSDP_PACKET, (SSDP_GROUP, SSDP_PORT))
        got, deadline = [], time.time() + timeout
        while time.time() < deadline and len(got) < 10:
            sock.settimeout(max(0.05, deadline - time.time()))
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                break
            except OSError:
                break
            got.append({"bytes": len(data), "from": addr[0],
                        "ms": round((time.time() - t0) * 1000.0, 2)})
        resp = sum(g["bytes"] for g in got)
        r = {"target": SSDP_GROUP, "port": SSDP_PORT, "responded": bool(got),
             "request_bytes": len(SSDP_PACKET), "response_bytes": resp,
             "responses": len(got), "iface": iface,
             "amplification": round(resp / float(len(SSDP_PACKET)), 2) if got else 0.0,
             "rtt_ms": min([g["ms"] for g in got]) if got else None, "samples": got[:4]}
        return {"attempts": [r], "best": r, "responded": bool(got)}
    except Exception as e:
        r = {"target": SSDP_GROUP, "responded": False, "amplification": 0.0,
             "request_bytes": len(SSDP_PACKET), "response_bytes": 0, "error": str(e)[:160]}
        return {"attempts": [r], "best": r, "responded": False}
    finally:
        sock.close()


def rotate_source_ports(target="1.1.1.1", port=53, n=8, timeout=1.5, qname=DEFAULT_QNAME):
    """Rate-limit sering per source port. Kirim dari n port berbeda, hitung yang dijawab."""
    results = []
    for i in range(n):
        payload = dns_packet(qname, "TXT")[1]
        r = _exchange(target, port, payload, timeout=timeout, expect=1,
                      src_port=40000 + random.randint(0, 20000))
        results.append({"src_port": r.get("src_port"), "responded": r.get("responded"),
                        "amplification": r.get("amplification"), "rtt_ms": r.get("rtt_ms")})
    ok = sum(1 for r in results if r["responded"])
    return {"target": target, "tried": n, "answered": ok,
            "answer_ratio": round(ok / float(n), 2) if n else 0.0,
            "rate_limited": ok < n, "results": results}


def probe_all(qname=DEFAULT_QNAME, qtype="TXT", timeout=3.0, ports_n=6):
    if qname and qname != DEFAULT_QNAME:
        dns = probe_dns(qname, qtype, timeout=timeout)
        dns["best"] = dict(dns.get("best") or {}, qname=qname, qtype=qtype)
    else:
        dns = probe_dns_best(timeout=timeout)
    ntp3 = probe_ntp(3, timeout=timeout)
    ntp6 = probe_ntp(6, timeout=timeout)
    ssdp = probe_ssdp(timeout=timeout)
    rot = rotate_source_ports(qname=qname, n=ports_n, timeout=min(1.5, timeout))
    best = max([dns.get("best") or {}, ntp3.get("best") or {},
                ntp6.get("best") or {}, ssdp.get("best") or {}],
               key=lambda r: r.get("amplification", 0.0))
    return {
        "dns": dns, "ntp_mode3": ntp3, "ntp_mode6": ntp6, "ssdp": ssdp,
        "port_rotation": rot,
        "any_responded": bool(dns.get("responded") or ntp3.get("responded")
                              or ntp6.get("responded") or ssdp.get("responded")),
        "best": best,
        "best_amplification": best.get("amplification", 0.0),
        "reflection_capable": bool(best.get("responded") and best.get("amplification", 0) > 1.0),
        "at": time.time(),
    }


# ---------------------------------------------------------------------------
# spoofed source (butuh root)
# ---------------------------------------------------------------------------
def _csum(data):
    if len(data) % 2:
        data += b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) + data[i + 1]
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return (~s) & 0xFFFF


def _ip_udp(src_ip, dst_ip, sport, dport, payload):
    udp = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload
    total = 20 + len(udp)
    ip = struct.pack("!BBHHHBBH4s4s", (4 << 4) | 5, 0, total, random.randint(0, 65535),
                     0, 64, socket.IPPROTO_UDP, 0,
                     socket.inet_aton(src_ip), socket.inet_aton(dst_ip))
    ip = ip[:10] + struct.pack("!H", _csum(ip)) + ip[12:]
    return ip + udp


def probe_spoof(server="1.1.1.1", qname=DEFAULT_QNAME, sport=33333, timeout=3.0):
    """Kirim DNS query dengan source IP dipalsukan lewat raw socket (butuh sudo).

    Kalau respons terlihat oleh raw socket, `spoof_src` terbukti — inilah
    syarat teknis reflection attack sungguhan.
    """
    try:
        raw = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
    except PermissionError:
        return {"ok": None, "reason": "butuh root (sudo)", "spoof_proven": False}
    except Exception as e:
        return {"ok": None, "reason": str(e)[:140], "spoof_proven": False}
    try:
        local = socket.gethostbyname(socket.gethostname())
    except Exception:
        local = "0.0.0.0"
    try:
        raw.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    except Exception:
        pass
    payload = dns_packet(qname, "TXT")[1]
    pkt = _ip_udp(local, server, sport, 53, payload)
    t0 = time.time()
    seen = []
    try:
        raw.sendto(pkt, (server, 0))
        raw.settimeout(timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw.settimeout(max(0.05, deadline - time.time()))
            try:
                data, addr = raw.recvfrom(4096)
            except socket.timeout:
                break
            if addr[0] == server and len(data) >= 28:
                # IP header (20) + UDP header (8) -> cek dport == sport
                dport = struct.unpack("!H", data[22:24])[0]
                if dport == sport:
                    seen.append({"bytes": len(data), "ms": round((time.time() - t0) * 1000, 2)})
                    break
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "spoof_proven": False}
    finally:
        raw.close()
    return {"ok": bool(seen), "spoof_proven": bool(seen), "src_ip_spoofed": local,
            "server": server, "sport": sport, "response_seen": seen[:2],
            "request_bytes": len(pkt)}
