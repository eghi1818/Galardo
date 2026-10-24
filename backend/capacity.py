"""Galardo - pengukur kapasitas (KNEE) target.

Bukan load-tester generik: keluaran yang dicari adalah ANGKA KNEE (titik latency melonjak /
error muncul) + TTR (lama degradasi) + puncak RPS. Semua pakai stdlib (threading + urllib).
"""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request

__all__ = ["run", "knee", "ttr", "ringkasan", "ringkas_teks", "describe"]

AMBANG_P95 = 2.0
AMBANG_ERR = 0.05


def _persen(nilai, q):
    if not nilai:
        return None
    s = sorted(nilai)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return round(s[i], 4)


def _satu_step(url, konkurensi, detik, timeout):
    hasil = {"ok": 0, "err": 0, "lat": [], "kode": {}}
    lock = threading.Lock()
    batas = time.time() + detik

    def kerja():
        while time.time() < batas:
            t0 = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "galardo-capacity"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    r.read(64)
                    kode = r.status
                dt = time.time() - t0
                with lock:
                    hasil["ok"] += 1
                    hasil["lat"].append(dt)
                    hasil["kode"][kode] = hasil["kode"].get(kode, 0) + 1
            except urllib.error.HTTPError as e:
                dt = time.time() - t0
                with lock:
                    hasil["err"] += 1
                    hasil["lat"].append(dt)
                    hasil["kode"][e.code] = hasil["kode"].get(e.code, 0) + 1
            except Exception:
                with lock:
                    hasil["err"] += 1

    ts = [threading.Thread(target=kerja, daemon=True) for _ in range(int(konkurensi))]
    t0 = time.time()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    durasi = max(0.001, time.time() - t0)
    total = hasil["ok"] + hasil["err"]
    return {
        "konkurensi": int(konkurensi),
        "detik": round(durasi, 3),
        "total": total,
        "ok": hasil["ok"],
        "err": hasil["err"],
        "rps": round(total / durasi, 2),
        "err_rate": (round(hasil["err"] / total, 4) if total else None),
        "p50": _persen(hasil["lat"], 0.50),
        "p95": _persen(hasil["lat"], 0.95),
        "kode": hasil["kode"],
    }


def knee(steps, ambang_p95=AMBANG_P95, ambang_err=AMBANG_ERR):
    """Titik pertama (menaik) yang p95-nya > ambang x baseline atau err_rate > ambang."""
    dasar = None
    for s in steps:
        if s.get("total"):
            dasar = s.get("p95")
            break
    for i, s in enumerate(steps):
        if not s.get("total"):
            continue
        if s.get("err_rate") is not None and s["err_rate"] > ambang_err:
            return {"index": i, "konkurensi": s["konkurensi"],
                    "alasan": "err_rate %.1f%% > %.1f%%" % (100 * s["err_rate"], 100 * ambang_err)}
        if dasar and s.get("p95") and s["p95"] > ambang_p95 * dasar:
            return {"index": i, "konkurensi": s["konkurensi"],
                    "alasan": "p95 %.3fs > %.1fx baseline %.3fs" % (s["p95"], ambang_p95, dasar)}
    return {"index": None, "konkurensi": None, "alasan": "belum terdeteksi pada rentang ini"}


def ttr(steps, ambang_p95=AMBANG_P95, ambang_err=AMBANG_ERR):
    """Perkiraan lama degradasi (detik) sejak knee sampai step terakhir yang masih memburuk."""
    k = knee(steps, ambang_p95, ambang_err)
    if k["index"] is None:
        return {"detik_degradasi": 0.0, "langkah": 0}
    dasar = None
    for s in steps:
        if s.get("total"):
            dasar = s.get("p95")
            break
    total_detik = 0.0
    langkah = 0
    for s in steps[k["index"]:]:
        buruk = (s.get("err_rate") is not None and s["err_rate"] > ambang_err) or \
                (dasar and s.get("p95") and s["p95"] > ambang_p95 * dasar)
        if buruk:
            total_detik += float(s.get("detik") or 0)
            langkah += 1
    return {"detik_degradasi": round(total_detik, 3), "langkah": langkah}


def ringkasan(steps):
    puncak = None
    for s in steps:
        if s.get("total") and (puncak is None or s["rps"] > puncak["rps"]):
            puncak = s
    tot_ok = sum(s.get("ok", 0) for s in steps)
    tot_err = sum(s.get("err", 0) for s in steps)
    return {
        "total_ok": tot_ok,
        "total_err": tot_err,
        "max_rps": puncak["rps"] if puncak else None,
        "max_rps_konkurensi": puncak["konkurensi"] if puncak else None,
    }


def run(url, steps=(1, 2, 4, 8, 16), detik=2.0, timeout=5.0,
        ambang_p95=AMBANG_P95, ambang_err=AMBANG_ERR):
    hasil = [_satu_step(url, int(k), float(detik), float(timeout)) for k in steps]
    return {
        "url": url,
        "steps": hasil,
        "knee": knee(hasil, ambang_p95, ambang_err),
        "ttr": ttr(hasil, ambang_p95, ambang_err),
        "ringkasan": ringkasan(hasil),
    }


def ringkas_teks(h):
    b = ["url: %s" % h.get("url")]
    b.append("%-11s %-7s %-7s %-9s %-9s %-7s" % ("konkurensi", "total", "err", "rps", "p95(s)", "err%"))
    for s in h.get("steps", []):
        b.append("%-11s %-7s %-7s %-9s %-9s %-7s" % (
            s["konkurensi"], s["total"], s["err"], s["rps"],
            ("%.3f" % s["p95"]) if s["p95"] is not None else "-",
            ("%.1f" % (100 * s["err_rate"])) if s["err_rate"] is not None else "-"))
    k = h.get("knee") or {}
    b.append("knee: %s" % (("konkurensi %s (%s)" % (k.get("konkurensi"), k.get("alasan")))
                           if k.get("index") is not None else "belum terdeteksi pada rentang ini"))
    b.append("TTR: %s detik degradasi" % (h.get("ttr") or {}).get("detik_degradasi", 0))
    r = h.get("ringkasan") or {}
    b.append("puncak: %s rps @ konkurensi %s" % (r.get("max_rps"), r.get("max_rps_konkurensi")))
    return "\n".join(b)


def describe():
    return {
        "keluaran": ["steps", "knee", "ttr", "ringkasan"],
        "ambang_p95": AMBANG_P95,
        "ambang_err": AMBANG_ERR,
        "prinsip": "angka knee + TTR, bukan throughput saja",
    }
