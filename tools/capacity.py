#!/usr/bin/env python3
"""CLI: ukur kapasitas (knee) target. Contoh: python3 tools/capacity.py --url http://127.0.0.1:8090"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import capacity as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Galardo - ukur kapasitas (knee) target")
    ap.add_argument("--url", required=True)
    ap.add_argument("--steps", default="1,2,4,8,16")
    ap.add_argument("--detik", type=float, default=3.0)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    steps = [int(x) for x in a.steps.split(",") if x.strip()]
    h = C.run(a.url, steps=steps, detik=a.detik, timeout=a.timeout)
    print(json.dumps(h, indent=2) if a.json else C.ringkas_teks(h))
    return 0 if h["ringkasan"]["total_ok"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
