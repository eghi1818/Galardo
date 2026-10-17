"""GALARDO - runner: lab target + API + dashboard in one process (MVP vertical slice).

Port policy (no conflicts with existing services):
- prefers API :8090 and lab target :8095
- if a port is taken by ANY process, scans upward in its range until free
- prints the final ports and uses them everywhere (seed, dashboard hint)

Usage:
  python3 run_local.py              # start everything, seed lab data
  python3 run_local.py --no-target  # API+dashboard only
  python3 run_local.py --reset      # wipe state and reseed
"""
import argparse
import os
import shutil
import socket
import sys
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

API_PREF = 8090
TARGET_PREF = 8095


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((os.environ.get("GALARDO_BIND", "127.0.0.1"), port))
            return True
        except OSError:
            return False


def pick_port(preferred, lo, hi, label):
    if port_free(preferred):
        return preferred
    print(f"[run_local] port {preferred} ({label}) is taken by another process -> scanning {lo}..{hi}")
    for p in range(lo, hi + 1):
        if port_free(p):
            print(f"[run_local] {label} will use port {p}")
            return p
    raise SystemExit(f"[run_local] no free port for {label} in {lo}..{hi}")


def reset_state():
    data_dir = os.path.normpath(os.path.join(BASE, "..", "data"))
    if os.path.exists(data_dir):
        shutil.rmtree(data_dir)
        print(f"[run_local] wiped {data_dir}")


def wait_http(url, timeout=10):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-target", action="store_true")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    if args.reset:
        reset_state()

    api_port = pick_port(API_PREF, 8090, 8099, "API+dashboard")
    target_port = None if args.no_target else pick_port(TARGET_PREF, 8095, 8099, "lab target")

    # target origin must be known before seeding
    if target_port:
        os.environ["GALARDO_TARGET_ORIGIN"] = f"http://{os.environ.get('GALARDO_BIND', '127.0.0.1')}:{target_port}"

    import lab_target
    import api

    if target_port:
        threading.Thread(target=lab_target.serve, kwargs={"port": target_port},
                         daemon=True).start()
        if wait_http(f"http://{os.environ.get('GALARDO_BIND', '127.0.0.1')}:{target_port}/healthz"):
            print(f"[run_local] lab target ready  -> http://{os.environ.get('GALARDO_BIND', '127.0.0.1')}:{target_port}")

    print("=" * 62)
    print(f"  GALARDO dashboard : http://{os.environ.get('GALARDO_BIND', '127.0.0.1')}:{api_port}/")
    print(f"  API base         : http://{os.environ.get('GALARDO_BIND', '127.0.0.1')}:{api_port}/api/v1")
    print("=" * 62)
    api.serve(port=api_port)  # blocks; seeds lab on boot


if __name__ == "__main__":
    main()
