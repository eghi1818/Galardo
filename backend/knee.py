"""GALARDO - estimasi titik knee (plafon) dari data beban bertahap.

Kenapa perlu
------------
Spike tanpa tahu plafon = menembak buta. Kalau plafon target 500 rps dan kita
tembak 5000, hasilnya "tumbang" tapi bukan karena kapasitas aslinya; kalau
plafonnya 50.000, 5000 tidak menyentuh apa pun.

tools/galardo_capacity.py butuh endpoint /control/capacity yang HANYA ada di lab
target. Untuk situs nyata, plafon harus DISIMPULKAN dari data yang kita ukur
sendiri: rps, latensi, dan error. Modul ini melakukan itu -- logika murni,
tanpa I/O, supaya bisa diuji tanpa jaringan.

Tiga pemicu, diambil yang PALING AWAL:
  latency_bend : p95 menembus baseline * factor
  rps_plateau  : rps tidak naik SEBANDING kenaikan vus (perbandingan relatif)
  error_onset  : tingkat error melewati ambang
"""

from __future__ import annotations

__all__ = ["estimate", "recommend", "summarize", "TRIGGERS",
           "DEFAULT_LATENCY_FACTOR", "DEFAULT_PLATEAU_DELTA", "DEFAULT_ERROR_RATE"]

TRIGGERS = ("latency_bend", "rps_plateau", "error_onset")

DEFAULT_LATENCY_FACTOR = 2.0
# Toleransi kekurangan relatif rps terhadap kenaikan vus (kecil = sangat sensitif).
# 0.75 dipilih karena pada ramp berbasis THREAD, rps sering tumbuh sublinear
# walau target sehat (GIL + scheduling) -- dengan 0.10 hampir semua ramp
# langsung salah dianggap jenuh.
DEFAULT_PLATEAU_DELTA = 0.75
DEFAULT_ERROR_RATE = 0.01


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _norm(samples):
    out = []
    for s in samples or []:
        if not isinstance(s, dict):
            continue
        out.append({
            "vus": _num(s.get("vus")),
            "rps": _num(s.get("rps")),
            "p50_ms": _num(s.get("p50_ms", s.get("p50"))),
            "p95_ms": _num(s.get("p95_ms", s.get("p95"))),
            "errors": _num(s.get("errors")),
            "sent": _num(s.get("sent")),
        })
    out.sort(key=lambda x: x["vus"])
    return out


def _err_rate(s):
    return (s["errors"] / s["sent"]) if s["sent"] else 0.0


def _latency_index(ss, baseline_p95, factor):
    if not baseline_p95 or baseline_p95 <= 0:
        return None
    limit = baseline_p95 * factor
    for i, s in enumerate(ss):
        if s["p95_ms"] >= limit:
            return i
    return None


def _plateau_index(ss, delta):
    """Jenuh kalau rps TIDAK naik sebanding dengan kenaikan vus.

    Perbandingan dilakukan RELATIF (rgain vs vgain), bukan ambang absolut,
    supaya benar untuk rentang vus apa pun. delta = toleransi kekurangan
    relatif; delta kecil berarti lebih sensitif. Default longgar (0.75) agar
    pertumbuhan sublinear yang normal tidak dianggap saturasi.
    """
    for i in range(1, len(ss)):
        prev, cur = ss[i - 1], ss[i]
        dv = cur["vus"] - prev["vus"]
        if dv <= 0:
            if cur["rps"] <= prev["rps"]:
                return i
            continue
        vgain = dv / max(prev["vus"], 1e-9)
        rgain = (cur["rps"] - prev["rps"]) / max(prev["rps"], 1e-9)
        if rgain < vgain * (1.0 - delta):
            return i
    return None


def _error_index(ss, rate):
    for i, s in enumerate(ss):
        if _err_rate(s) >= rate:
            return i
    return None


def estimate(samples, baseline_p95=None, latency_factor=DEFAULT_LATENCY_FACTOR,
             plateau_delta=DEFAULT_PLATEAU_DELTA, error_rate=DEFAULT_ERROR_RATE):
    """Perkirakan titik knee. Selalu mengembalikan dict, tidak pernah melempar."""
    ss = _norm(samples)
    if len(ss) < 3:
        return {"ok": False, "knee": None, "quality": "unknown",
                "reason": "butuh minimal 3 titik, ada %d" % len(ss),
                "series": ss, "triggers": {}, "confidence": "low"}

    base = baseline_p95 or ss[0]["p95_ms"] or None

    trig = {}
    for name, idx in ((TRIGGERS[0], _latency_index(ss, base, latency_factor)),
                      (TRIGGERS[1], _plateau_index(ss, plateau_delta)),
                      (TRIGGERS[2], _error_index(ss, error_rate))):
        if idx is not None:
            trig[name] = idx

    if not trig:
        return {"ok": True, "knee": None, "quality": "no_knee",
                "reason": "tidak ada tanda jenuh; plafon di atas titik terakhir",
                "series": ss, "triggers": {}, "confidence": "low",
                "baseline_p95": base, "last": ss[-1]}

    idx = min(trig.values())
    agree = sorted(k for k, v in trig.items() if abs(v - idx) <= 1)
    conf = "high" if len(agree) >= 3 else ("medium" if len(agree) == 2 else "low")
    k = ss[idx]
    return {
        "ok": True,
        "knee": {"vus": k["vus"], "rps": k["rps"], "p95_ms": k["p95_ms"], "index": idx},
        "quality": "sharp" if conf == "high" else "gradual",
        "reason": "knee di vus=%g rps=%.1f p95=%.1fms (pemicu: %s)"
                  % (k["vus"], k["rps"], k["p95_ms"], ",".join(sorted(trig))),
        "series": ss, "triggers": trig, "agreeing": agree,
        "confidence": conf, "baseline_p95": base,
    }


def recommend(knee, multiplier=2.5, hold_seconds=60, max_vus=20000):
    """Saran parameter spike dari knee. Selalu mengembalikan dict."""
    if not knee:
        return {"target_vus": None, "target_rps": None, "ramp_seconds": 60,
                "hold_seconds": hold_seconds, "multiplier": multiplier,
                "reason": "knee belum terukur - pakai ramp bertahap, jangan spike"}
    tv = int(min(max(knee["vus"] * multiplier, knee["vus"] + 10), max_vus))
    tr = round(knee["rps"] * multiplier, 1)
    ramp = max(30, min(300, int(tv / 5)))
    return {"target_vus": tv, "target_rps": tr, "ramp_seconds": ramp,
            "hold_seconds": hold_seconds, "multiplier": multiplier,
            "reason": "spike %.1fx knee (vus=%g rps=%.1f)" % (multiplier, knee["vus"], knee["rps"])}


def summarize(result):
    if not isinstance(result, dict):
        return "knee tidak tersedia"
    k = result.get("knee")
    if not k:
        return "knee=- mutu=%s keyakinan=%s | %s" % (
            result.get("quality"), result.get("confidence"), result.get("reason"))
    return "knee vus=%g rps=%.1f p95=%.1fms mutu=%s keyakinan=%s | %s" % (
        k["vus"], k["rps"], k["p95_ms"], result.get("quality"),
        result.get("confidence"), result.get("reason"))
