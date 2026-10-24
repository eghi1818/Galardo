#!/usr/bin/env python3
"""CLI: cek url dari banyak negara. Contoh: python3 tools/checkhost.py --url portalyogya.com"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import checkhost as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Galardo - check-host per-negara")
    ap.add_argument("--url", required=True)
    ap.add_argument("--max-nodes", type=int, default=5)
    ap.add_argument("--batas", type=float, default=12.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    h = C.probe(a.url, max_nodes=a.max_nodes, batas=a.batas)
    if a.json:
        print(json.dumps(h, indent=2))
    else:
        print("url: %s" % h["url"])
        print("catatan: %s" % h["catatan"])
        for b in h["baris"]:
            print("  %-4s %-14s %-8s %s" % (b["negara"], b["kota"][:14],
                                            "OK" if b["ok"] else ("GAGAL" if b["ok"] is False else "?"),
                                            (("%.3fs" % b["waktu"]) if b["waktu"] is not None else (b["err"] or ""))))
        print("VERDICT: %s" % h["ringkasan"]["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
