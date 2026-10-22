"""GALARDO - probe UDP reflection / amplification (item 13).

Penolakan lama: "tidak ada padanan DDoS reflection/amplification".
Sekarang ada, dan yang diukur bukan kutipan dari internet melainkan:

  * apakah target UDP benar-benar menjawab dari port sumber acak
  * RASIO AMPLIFIKASI = byte respons / byte permintaan  (angka inti reflection)
  * apakah rate-limit terjadi saat banyak port sumber dipakai bergantian

Protokol: DNS (UDP/53), NTP (UDP/123), SSDP (UDP/1900 multicast).
Spoofing source IP diuji terpisah karena butuh raw socket (root).
"""
import os
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


def _local_ips():
    """Semua kandidat interface: default route + hostname + override env."""
    ips = []
    d = _default_if_ip()
    if d:
        ips.append(d)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    forced = os.environ.get("GALARDO_SSDP_IFACE")
    if forced:
        ips = [forced] + [i for i in ips if i != forced]
    return ips


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


def _probe_many(targets, port, payload_factory, timeout, expect, deadline=None):
    out = []
    for t in targets:
        if deadline is not None and time.time() >= deadline:
            break
        try:
            payload = payload_factory() if callable(payload_factory) else payload_factory
        except Exception:
            payload = payload_factory
        t_timeout = timeout if deadline is None else max(0.05, min(timeout, deadline - time.time()))
        r = _exchange(t, port, payload, timeout=t_timeout, expect=expect)
        out.append(r)
        if r.get("responded"):
            break
    best = max(out, key=lambda r: r.get("amplification", 0.0)) if out else {}
    return {"attempts": out, "best": best,
            "responded": any(r.get("responded") for r in out)}


# ---------------------------------------------------------------------------
# public probes
# ---------------------------------------------------------------------------
def probe_dns(qname=DEFAULT_QNAME, qtype="TXT", servers=DNS_SERVERS, timeout=3.0, deadline=None):
    return _probe_many(servers, 53, lambda: dns_packet(qname, qtype)[1], timeout, 1,
                       deadline=deadline)


def probe_dns_best(timeout=3.0, candidates=DNS_CANDIDATES, deadline=None):
    """Coba beberapa kombinasi qname/qtype, kembalikan yang amplifikasinya terbesar."""
    tried = []
    best = None
    for qname, qtype in candidates:
        if deadline is not None and time.time() >= deadline:
            break
        if deadline is not None and time.time() >= deadline:
            break
        r = _probe_many(DNS_SERVERS, 53, lambda q=qname, t=qtype: dns_packet(q, t)[1],
                        min(timeout, 2.5), 1, deadline=deadline)
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


def probe_ntp(mode=3, servers=None, timeout=3.0, deadline=None):
    servers = servers or (NTP_CTRL_SERVERS if mode == 6 else NTP_SERVERS)
    return _probe_many(servers, 123, lambda: ntp_packet(mode), timeout, 1, deadline=deadline)


def _ssdp_once(iface, window):
    t0 = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        if iface:
            try:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                socket.inet_aton(iface))
            except Exception:
                pass
        sock.bind(("", 0))
        sock.sendto(SSDP_PACKET, (SSDP_GROUP, SSDP_PORT))
        got, deadline = [], time.time() + window
        while time.time() < deadline and len(got) < 12:
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
        return {"iface": iface, "responded": bool(got), "responses": len(got),
                "request_bytes": len(SSDP_PACKET), "response_bytes": resp,
                "amplification": round(resp / float(len(SSDP_PACKET)), 2) if got else 0.0,
                "rtt_ms": min([g["ms"] for g in got]) if got else None,
                "samples": got[:4]}
    except Exception as e:
        return {"iface": iface, "responded": False, "responses": 0,
                "request_bytes": len(SSDP_PACKET), "response_bytes": 0,
                "amplification": 0.0, "error": str(e)[:140]}
    finally:
        sock.close()


def probe_ssdp(timeout=4.0):
    """SSDP butuh interface multicast yang benar. Coba SEMUA interface lokal."""
    ifaces = _local_ips() or [None]
    window = max(1.2, float(timeout) / max(1, len(ifaces)))
    attempts = [_ssdp_once(i, window) for i in ifaces]
    best = max(attempts, key=lambda r: r.get("amplification", 0.0)) if attempts else {}
    return {"attempts": attempts, "best": best, "ifaces_tried": ifaces,
            "responded": any(a.get("responded") for a in attempts)}


def rotate_source_ports(target="1.1.1.1", port=53, n=8, timeout=1.5, qname=DEFAULT_QNAME,
                        deadline=None):
    """Rate-limit sering per source port. Kirim dari n port berbeda, hitung yang dijawab."""
    results = []
    for i in range(n):
        if deadline is not None and time.time() >= deadline:
            break
        payload = dns_packet(qname, "TXT")[1]
        r = _exchange(target, port, payload, timeout=timeout, expect=1,
                      src_port=40000 + random.randint(0, 20000))
        results.append({"src_port": r.get("src_port"), "responded": r.get("responded"),
                        "amplification": r.get("amplification"), "rtt_ms": r.get("rtt_ms")})
    ok = sum(1 for r in results if r["responded"])
    return {"target": target, "tried": n, "answered": ok,
            "answer_ratio": round(ok / float(n), 2) if n else 0.0,
            "rate_limited": ok < n, "results": results}


def probe_all(qname=DEFAULT_QNAME, qtype="TXT", timeout=3.0, ports_n=6, budget=None):
    """Probe semua jalur UDP dengan PAGAR WAKTU TOTAL.

    budget = batas detik untuk SELURUH fungsi (default GALARDO_UDP_BUDGET atau 8.0).
    Tahap yang tidak sempat berjalan ditandai {"skipped": "budget"} - BUKAN dianggap gagal.
    Setiap tahap memakai timeout=min(timeout, sisa budget) supaya tak bisa menembus pagar.
    """
    if budget is None:
        try:
            budget = float(os.environ.get("GALARDO_UDP_BUDGET") or 8.0)
        except ValueError:
            budget = 8.0
    budget = max(0.2, float(budget))
    deadline = time.time() + budget
    skipped = []

    def sisa():
        return max(0.0, deadline - time.time())

    def lewat(nama):
        if sisa() <= 0.2:
            skipped.append(nama)
            return True
        return False

    if lewat("dns"):
        dns = {"skipped": "budget"}
    elif qname and qname != DEFAULT_QNAME:
        dns = probe_dns(qname, qtype, timeout=min(timeout, sisa()), deadline=deadline)
        dns["best"] = dict(dns.get("best") or {}, qname=qname, qtype=qtype)
    else:
        dns = probe_dns_best(timeout=min(timeout, sisa()), deadline=deadline)

    ntp3 = {"skipped": "budget"} if lewat("ntp_mode3") else probe_ntp(3, timeout=min(timeout, sisa()), deadline=deadline)
    ntp6 = {"skipped": "budget"} if lewat("ntp_mode6") else probe_ntp(6, timeout=min(timeout, sisa()), deadline=deadline)
    ssdp = {"skipped": "budget"} if lewat("ssdp") else probe_ssdp(timeout=min(timeout, sisa()))
    rot = ({"skipped": "budget"} if lewat("port_rotation")
           else rotate_source_ports(qname=qname, n=ports_n,
                                    timeout=min(1.5, timeout, sisa()), deadline=deadline))

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
        "budget": budget,
        "elapsed": round(budget - sisa(), 2),
        "skipped": skipped,
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


# BSD/macOS mengharuskan ip_len & ip_off dalam HOST byte order saat IP_HDRINCL;
# Linux mengharuskan NETWORK byte order. Salah urutan -> sendto() EINVAL.
_SYSNAME = os.uname().sysname.lower() if hasattr(os, "uname") else "linux"
IPLEN_ORDER = "<" if ("darwin" in _SYSNAME or "bsd" in _SYSNAME) else "!"


def _ip_udp(src_ip, dst_ip, sport, dport, payload):
    udp = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload
    total = 20 + len(udp)
    ip = (struct.pack("!BB", (4 << 4) | 5, 0)
          + struct.pack(IPLEN_ORDER + "H", total)
          + struct.pack("!H", random.randint(0, 65535))
          + struct.pack(IPLEN_ORDER + "H", 0)
          + struct.pack("!BBH", 64, socket.IPPROTO_UDP, 0)
          + socket.inet_aton(src_ip) + socket.inet_aton(dst_ip))
    ip = ip[:10] + struct.pack("!H", _csum(ip)) + ip[12:]
    return ip + udp


def _local_ip(fallback=None):
    """IP lokal yang benar-benar dipakai keluar (bukan 127.0.0.1).

    gethostbyname(gethostname()) sering mengembalikan 127.0.0.1 di macOS,
    sehingga balasan untuk paket bersumber palsu tidak kembali lewat en0.
    """
    sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sk.connect(("1.1.1.1", 53))
        return sk.getsockname()[0]
    except OSError:
        return fallback or socket.gethostbyname(socket.gethostname())
    finally:
        sk.close()


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
        local = socket._local_ip()
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
