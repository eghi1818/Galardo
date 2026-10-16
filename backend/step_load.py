#!/usr/bin/env python3
"""GALARDO step-load tool - single-target, exact-RPS load run with live metrics.

Usage: step_load.py <url> <rps> <duration_sec> [timeout_ms]
Designed for authorized capacity testing of owner-controlled targets.
Exact RPS via token bucket; progress + interim metrics every 5s.
"""
import json
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request

def main():
    if len(sys.argv) < 4:
        print("usage: step_load.py <url> <rps> <duration_sec> [timeout_ms]")
        sys.exit(2)
    url, rps, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    timeout_ms = int(sys.argv[4]) if len(sys.argv) > 4 else 4000
    buster = not os.environ.get("GALARDO_NO_BUSTER")

    lock = threading.Lock()
    stats = {"n": 0, "ok": 0, "e4": 0, "e5": 0, "to": 0, "ce": 0, "ch": 0,
             "lat": [], "bytes": 0, "codes": {}}
    stop = threading.Event()

    class TokenBucket:
        def __init__(self, rate):
            self.rate = rate
            self.tokens = 0.0
            self.last = time.time()
        def take(self):
            while not stop.is_set():
                with lock:
                    now = time.time()
                    self.tokens = min(self.rate, self.tokens + (now - self.last) * self.rate)
                    self.last = now
                    if self.tokens >= 1.0:
                        self.tokens -= 1.0
                        return True
                    wait = (1.0 - self.tokens) / self.rate
                stop.wait(min(wait, 0.25))
            return False

    bucket = TokenBucket(rps)

    def worker():
        ctx = ssl.create_default_context()
        while not stop.is_set():
            if not bucket.take():
                break
            u = url
            hdrs = {"User-Agent": "galardo-stepload/1.0 (authorized capacity test)",
                    "Accept": "*/*", "Connection": "close"}
            if buster:
                u, _n = cb.decorate(url)
                hdrs.update(cb.NO_CACHE_HEADERS)
            req = urllib.request.Request(u, headers=hdrs)
            t0 = time.time()
            code = err = None
            cache_hit = False
            try:
                with urllib.request.urlopen(req, timeout=timeout_ms / 1000.0, context=ctx) as r:
                    b = r.read(32768)
                    code = r.status
                    rb = len(b)
                    try:
                        cache_hit = not cb.pierce_ok(dict(r.headers))
                    except Exception:
                        cache_hit = False
            except urllib.error.HTTPError as e:
                code = e.code
                rb = 0
            except (socket.timeout, TimeoutError):
                err = "to"; rb = 0
            except Exception:
                err = "ce"; rb = 0
            dt = time.time() - t0
            with lock:
                stats["n"] += 1
                stats["bytes"] += rb
                if err == "to":
                    stats["to"] += 1
                elif err == "ce":
                    stats["ce"] += 1
                elif code:
                    stats["codes"][code] = stats["codes"].get(code, 0) + 1
                    if code < 400:
                        stats["ok"] += 1
                    elif code < 500:
                        stats["e4"] += 1
                    else:
                        stats["e5"] += 1
                stats["lat"].append(dt)
                if cache_hit:
                    stats["ch"] += 1

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(min(max(8, int(rps)), 256))]
    t0 = time.time()
    for t in threads:
        t.start()
    end = t0 + dur
    while time.time() < end:
        stop.wait(5)
        with lock:
            el = time.time() - t0
            n = stats["n"]
            lat = sorted(stats["lat"])
            p95 = lat[int(0.95 * (len(lat) - 1))] * 1000 if lat else 0
            print(f"  t+{el:5.0f}s  sent={n:6d}  actual_rps={n/el:7.1f}  "
                  f"ok={stats['ok']} 4xx={stats['e4']} 5xx={stats['e5']} to={stats['to']} ce={stats['ce']}  "
                  f"p95={p95:.0f}ms")
    stop.set()
    time.sleep(0.5)
    el = time.time() - t0
    with lock:
        lat = sorted(stats["lat"])

        def pct(p):
            i = int(round(p / 100 * (len(lat) - 1)))
            return round(lat[i] * 1000, 1) if lat else None
        print(json.dumps({
            "url": url, "target_rps": rps, "duration_actual": round(el, 1),
            "requests": stats["n"], "actual_rps": round(stats["n"] / el, 2),
            "ok": stats["ok"], "err_4xx": stats["e4"], "err_5xx": stats["e5"],
            "timeouts": stats["to"], "conn_errors": stats["ce"],
            "cache_buster": buster, "cache_hits": stats["ch"],
            "status_codes": stats["codes"],
            "p50_ms": pct(50), "p95_ms": pct(95), "p99_ms": pct(99),
            "bandwidth_kbps": round(stats["bytes"] * 8 / el / 1024, 1),
        }, indent=1))

if __name__ == "__main__":
    main()
