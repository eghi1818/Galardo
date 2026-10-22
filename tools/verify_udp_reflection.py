#!/usr/bin/env python3
"""Item 13: kunci semantik probe UDP reflection/amplification (backend/udp_probe.py).

Offline kecuali dua cek toleran (probe_spoof, rotate_source_ports nyata):
- A packet builder DNS/NTP/SSDP (struktur byte, mapping qtype, mode NTP)
- B matematika rasio amplifikasi lewat UDP server lokal
- C reflection_capable + pagar budget (monkeypatch, deterministik)
- D checksum IP + header UDP (jalur raw socket spoof) + bentuk keluaran probe_spoof
- E wiring endpoint /sources/*/udp di api.py
- F panggilan NYATA rotate_source_ports + probe_all (menangkap NameError)
Stdlib only. Exit 1 bila ada yang gagal.
"""
import os, re, socket, struct, sys, threading, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
import udp_probe as up  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


print("== A. packet builder ==")
_, pkt = up.dns_packet("isc.org", "DNSKEY", qid=0x1234)
check("A DNS qid ikut", struct.unpack("!H", pkt[:2])[0] == 0x1234)
check("A DNS flags query 0x0100", struct.unpack("!H", pkt[2:4])[0] == 0x0100)
check("A DNS qdcount=1", struct.unpack("!H", pkt[4:6])[0] == 1)
check("A DNS label berpanjang + root", pkt[12:21] == b"\x03isc\x03org\x00", pkt[12:21])
check("A DNS qtype DNSKEY=48 qclass=1", struct.unpack("!HH", pkt[21:25]) == (48, 1), pkt[21:25])
check("A mapping ANY=255", up.DNS_QTYPE["ANY"] == 255)
check("A mapping MX=15", up.DNS_QTYPE["MX"] == 15)
check("A qtype tak dikenal -> 16", struct.unpack("!H", up.dns_packet("x.org", "NGAWUR")[1][-4:-2])[0] == 16)

p3, p6 = up.ntp_packet(3), up.ntp_packet(6)
check("A NTP mode3 48 byte 0x1b", len(p3) == 48 and p3[0] == 0x1B, len(p3))
check("A NTP mode6 8 byte mode=6", len(p6) == 8 and (p6[0] & 0x07) == 6, p6[:1])
check("A SSDP punya M-SEARCH/MAN/ST/HOST",
      all(k in up.SSDP_PACKET for k in (b"M-SEARCH", b"ssdp:discover", b"ssdp:all",
                                       b"239.255.255.250:1900")))
check("A SSDP group & port", up.SSDP_GROUP == "239.255.255.250" and up.SSDP_PORT == 1900)

print("== B. rasio amplifikasi (UDP lokal) ==")
srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
srv.bind(("127.0.0.1", 0))
port = srv.getsockname()[1]
BALAS = b"z" * 185


def pelayan():
    try:
        srv.settimeout(3.0)
        _, addr = srv.recvfrom(4096)
        srv.sendto(BALAS, addr)
    except Exception:
        pass


th = threading.Thread(target=pelayan, daemon=True)
th.start()
r = up._exchange("127.0.0.1", port, b"q" * 25, timeout=2.0, expect=1)
th.join(timeout=3.0)
check("B responded True", r.get("responded") is True, r)
check("B request_bytes 25", r.get("request_bytes") == 25, r.get("request_bytes"))
check("B response_bytes 185", r.get("response_bytes") == 185, r.get("response_bytes"))
check("B amplification 7.4", r.get("amplification") == 7.4, r.get("amplification"))
check("B rtt dilaporkan", isinstance(r.get("rtt_ms"), (int, float)), r.get("rtt_ms"))
srv.close()

kosong = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
kosong.bind(("127.0.0.1", 0))
r2 = up._exchange("127.0.0.1", kosong.getsockname()[1], b"q" * 10, timeout=0.6, expect=1)
check("B tanpa penjawab -> responded False amp 0.0",
      r2.get("responded") is False and r2.get("amplification") == 0.0, r2)
kosong.close()

print("== C. reflection_capable & pagar budget ==")
asli = (up.probe_dns_best, up.probe_ntp, up.probe_ssdp, up.rotate_source_ports)


def palsu(amp):
    return lambda *a, **k: {"best": {"responded": amp > 0, "amplification": amp},
                            "responded": amp > 0, "attempts": []}


try:
    up.probe_dns_best = palsu(7.4)
    up.probe_ntp = palsu(1.2)
    up.probe_ssdp = palsu(0.0)
    up.rotate_source_ports = lambda *a, **k: {"answer_ratio": 1.0}
    rc = up.probe_all(budget=5.0)
    check("C best_amplification 7.4", rc.get("best_amplification") == 7.4, rc.get("best_amplification"))
    check("C reflection_capable True (>1.0)", rc.get("reflection_capable") is True, rc.get("reflection_capable"))
    # Keduanya harus di bawah 1.0. Catatan: ntp WAJIB ikut diturunkan, karena best
    # memakai max() - kalau ntp dibiarkan 1.2 ia tetap menang dan cek jadi palsu.
    up.probe_dns_best = palsu(0.5)
    up.probe_ntp = palsu(0.4)
    rc2 = up.probe_all(budget=5.0)
    check("C best_amplification 0.5", rc2.get("best_amplification") == 0.5, rc2.get("best_amplification"))
    check("C reflection_capable False (<=1.0)", rc2.get("reflection_capable") is False, rc2.get("reflection_capable"))

    # Pagar budget: floor budget (0.2) SAMA dengan ambang lewat() (0.2), sehingga tahap
    # pertama berada persis di batas dan pembulatan float menentukan. Empat tahap
    # terakhir yang pasti kena - itu yang dikunci. Fakes dipakai agar tanpa jaringan.
    rc3 = up.probe_all(budget=0.2)
    check("C budget 0.2 -> 4 tahap akhir ditandai skipped",
          set(rc3.get("skipped") or []) >= {"ntp_mode3", "ntp_mode6", "ssdp", "port_rotation"},
          rc3.get("skipped"))
    check("C best_amplification tetap angka >= 0",
          isinstance(rc3.get("best_amplification"), (int, float))
          and rc3["best_amplification"] >= 0.0, rc3.get("best_amplification"))
finally:
    up.probe_dns_best, up.probe_ntp, up.probe_ssdp, up.rotate_source_ports = asli

print("== D. raw packet & probe_spoof ==")
rp = up._ip_udp("192.0.2.10", "192.0.2.20", 33333, 53, b"abcd")
check("D urutan ip_len sesuai platform",
      up.IPLEN_ORDER == ("<" if (sys.platform == "darwin" or "bsd" in sys.platform) else "!"),
      up.IPLEN_ORDER)
check("D total length benar (urutan sesuai platform)",
      struct.unpack(up.IPLEN_ORDER + "H", rp[2:4])[0] == 32,
      struct.unpack(up.IPLEN_ORDER + "H", rp[2:4])[0])
check("D protokol 17", rp[9] == 17, rp[9])
hdr = rp[:20]
check("D checksum IP valid", up._csum(hdr[:10] + b"\x00\x00" + hdr[12:]) == struct.unpack("!H", hdr[10:12])[0],
      (up._csum(hdr[:10] + b"\x00\x00" + hdr[12:]), struct.unpack("!H", hdr[10:12])[0]))
check("D src/dst IP terpasang",
      rp[12:16] == socket.inet_aton("192.0.2.10") and rp[16:20] == socket.inet_aton("192.0.2.20"))
check("D header UDP sport/dport/len", struct.unpack("!HHH", rp[20:26]) == (33333, 53, 12), struct.unpack("!HHH", rp[20:26]))
check("D payload ikut", rp[28:] == b"abcd")

sp = up.probe_spoof(timeout=1.5)
check("D probe_spoof kembalikan ok & spoof_proven",
      isinstance(sp, dict) and "ok" in sp and "spoof_proven" in sp, sp)
check("D probe_spoof aman / beri alasan bila tanpa root",
      sp.get("ok") is not None or bool(sp.get("reason")), sp)

print("== E. wiring endpoint ==")
api = open(os.path.join(ROOT, "backend", "api.py"), encoding="utf-8").read()
check("E endpoint /sources/*/udp ada", '"/sources/*/udp"' in api)
check("E memanggil probe_all", "_up.probe_all(" in api)
check("E budget diteruskan", 'b.get("budget")' in api and "GALARDO_UDP_BUDGET" in api)
check("E capability udp hanya bila reflection_capable",
      re.search(r'if r\.get\("reflection_capable"\):\s*\n\s*_sc\.mark_proven\(m\[0\], \["udp"\]', api) is not None)
check("E capability spoof_src hanya bila spoof_proven",
      re.search(r'if \(r\.get\("spoof"\) or \{\}\)\.get\("spoof_proven"\):\s*\n\s*_sc\.mark_proven\(m\[0\], \["spoof_src"\]', api) is not None)
check("E spoof default aktif & dibatasi timeout",
      'b.get("spoof", True)' in api and "spoof_timeout" in api)

print("== F. panggilan NYATA (penangkap NameError) ==")
try:
    rot = up.rotate_source_ports(n=2, timeout=1.0)
    check("F rotate_source_ports jalan (bukan NameError)", "answer_ratio" in rot, rot)
except Exception as e:
    check("F rotate_source_ports jalan (bukan NameError)", False, "%s: %s" % (type(e).__name__, e))
try:
    rn = up.probe_all(budget=3.0, ports_n=2, timeout=1.0)
    check("F probe_all nyata selesai", isinstance(rn, dict) and "reflection_capable" in rn, str(rn)[:120])
    check("F tahap port_rotation ada", "port_rotation" in rn)
except Exception as e:
    check("F probe_all nyata selesai", False, "%s: %s" % (type(e).__name__, e))

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
