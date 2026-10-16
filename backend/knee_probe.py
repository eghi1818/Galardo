"""GALARDO - probe plafon (knee) ke target: ramp konkurensi bertahap.

Beda dengan tools/galardo_capacity.py yang butuh endpoint /control di LAB target,
modul ini bekerja ke situs APA PUN: naikkan konkurensi bertahap, ukur rps dan
persentil latensi, lalu serahkan ke backend/knee.py untuk disimpulkan.

Sengaja tidak memakai LoadEngine supaya tidak bergantung skenario -- cukup GET.
Memakai cache-buster supaya CDN tidak melayani salinan cache.

PENTING: 'rps' = throughput yang DICOBA (sent/elapsed), 'ok_rps' = yang BERHASIL.
Ke target mati, request gagal seketika sehingga 'rps' bisa tetap tinggi padahal
tidak ada satu pun yang berhasil -- plafon harus disimpulkan dari 'ok_rps'.
"""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request

try:
    from . import netssl as _ns
except ImportError:
    import netssl as _ns

try:
    from . import cachebuster as _cb
except ImportError:
    import cachebuster as _cb

__all__ = ["measure", "default_fetcher", "DEFAULT_STEPS", "DEFAULT_STEP_SECONDS"]

DEFAULT_STEPS = (4, 8, 16, 32)
DEFAULT_STEP_SECONDS = 2.5


def default_fetcher(url, timeout=2.0):
    """Kembalikan (status, error, latency_ms). Tidak pernah melempar."""
    t0 = time.time()
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": "galardo-knee/1.0", "Accept": "*/*",
        "Cache-Control": "no-cache, no-store, max-age=0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ns.context()) as r:
            r.read(8192)
            return r.status, None, (time.time() - t0) * 1000.0
    except urllib.error.HTTPError as e:
        return e.code, None, (time.time() - t0) * 1000.0
    except Exception as e:
        return 0, str(e)[:80], (time.time() - t0) * 1000.0


def _pct(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    idx = int(round((p / 100.0) * (len(sorted_vals) - 1)))
    return sorted_vals[max(0, min(idx, len(sorted_vals) - 1))]


def measure(origin, path="/", steps=DEFAULT_STEPS, step_seconds=DEFAULT_STEP_SECONDS,
            timeout=2.0, headers=None, fetcher=None):
    """Ramp konkurensi bertahap. Kembalikan dict dengan 'samples'."""
    f = fetcher or default_fetcher
    base = (origin or "").rstrip("/")
    url, _ = _cb.decorate(base + path, _cb.BUSTER_KEY, "knee")
    out = []
    t_start = time.time()
    for n in steps:
        n = int(n)
        stop = time.time() + float(step_seconds)
        lock = threading.Lock()
        sent = [0]
        ok = [0]
        bad = [0]
        lat = []

        def worker():
            while time.time() < stop:
                st, err, dt = f(url, timeout)
                with lock:
                    sent[0] += 1
                    if isinstance(st, int) and 200 <= st < 400:
                        ok[0] += 1
                    else:
                        bad[0] += 1
                    lat.append(dt)

        t0 = time.time()
        ths = [threading.Thread(target=worker, daemon=True) for _ in range(n)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        el = max(0.001, time.time() - t0)
        lat.sort()
        out.append({"vus": n, "sent": sent[0], "ok": ok[0], "errors": bad[0],
                    "rps": round(sent[0] / el, 2),
                    "ok_rps": round(ok[0] / el, 2),
                    "p50_ms": round(_pct(lat, 50), 2),
                    "p95_ms": round(_pct(lat, 95), 2),
                    "p99_ms": round(_pct(lat, 99), 2)})
    return {"url": url, "samples": out, "steps": len(out),
            "elapsed": round(time.time() - t_start, 2)}
