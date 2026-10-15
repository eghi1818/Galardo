#!/usr/bin/env python3
"""GALARDO - ukur amplifikasi UDP nyata dan tandai kapabilitas di registry."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

import envload  # noqa: E402
envload.load()

import srccap     # noqa: E402
import udp_probe  # noqa: E402

SID = "src-local-laptop"


def main():
    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    print("mode      :", "root -> spoof source IP diuji" if is_root else
          "user -> spoof dilewati (jalankan `make udp-spoof`)")
    print("qname     :", udp_probe.DEFAULT_QNAME, "(TXT)")
    print("-" * 66)

    r = udp_probe.probe_all()
    print("  %-12s %-10s %-8s %-9s %-10s %s"
          % ("protokol", "dijawab", "ratio", "req byte", "resp byte", "rtt ms"))
    for k in ("dns", "ntp_mode3", "ntp_mode6", "ssdp"):
        b = (r.get(k) or {}).get("best") or {}
        print("  %-12s %-10s %-8s %-9s %-10s %s"
              % (k, b.get("responded"), b.get("amplification"),
                 b.get("request_bytes"), b.get("response_bytes"), b.get("rtt_ms")))
    rot = r.get("port_rotation") or {}
    print("  %-12s %s/%s port dijawab | rate_limited=%s"
          % ("port-rotate", rot.get("answered"), rot.get("tried"), rot.get("rate_limited")))

    print("-" * 66)
    bd = (r.get("dns") or {}).get("best") or {}
    print("kombinasi DNS  :", bd.get("qname"), bd.get("qtype"), "->",
          bd.get("response_bytes"), "byte balasan (qname/qtype pemenang)")
    print("best ratio     :", r.get("best_amplification"))
    print("reflection OK  :", r.get("reflection_capable"))

    if is_root:
        sp = udp_probe.probe_spoof()
        print("spoof src IP   :", sp.get("spoof_proven"), "|", sp.get("reason") or sp.get("src_ip_spoofed"))
        if sp.get("spoof_proven"):
            srccap.ensure_local()
            srccap.mark_proven(SID, ["spoof_src"], {"spoof": sp})
            print("registry       : 'spoof_src' ditandai TERBUKTI")

    if r.get("reflection_capable"):
        srccap.ensure_local()
        s = srccap.mark_proven(SID, ["udp"], {"udp": r})
        print("registry       : 'udp' ditandai TERBUKTI ->", s.capabilities())

    print("-" * 66)
    print(json.dumps({k: r.get(k) for k in
                      ("best_amplification", "reflection_capable", "any_responded")},
                     indent=2))
    print("UDP_OK" if r.get("any_responded") else "UDP_TIDAK_ADA_RESPONS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
