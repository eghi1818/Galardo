"""Ekspor OTLP/HTTP JSON (metrics + span). Tanpa dependensi. Fail-open.

Aktif hanya bila GALARDO_OTLP_URL diisi (mis. http://127.0.0.1:4318).
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request

SCOPE = "galardo.engine"
STATS = {"exported": 0, "failed": 0, "skipped": 0, "last_error": None}
_LOCK = threading.Lock()


def enabled():
    return bool((os.environ.get("GALARDO_OTLP_URL") or "").strip())


def now_ns():
    return str(int(time.time() * 1000000000))


def _val(v):
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    return {"stringValue": str(v)}


def _attrs(d):
    return [{"key": str(k), "value": _val(v)} for k, v in sorted((d or {}).items())]


def metric(name, points, unit="1", kind="gauge"):
    dps = []
    for p in points:
        dp = {"timeUnixNano": str(p.get("ts_ns") or now_ns()),
              "attributes": _attrs(p.get("attrs"))}
        v = p.get("value")
        if isinstance(v, bool) or isinstance(v, int):
            dp["asInt"] = str(int(v))
        else:
            dp["asDouble"] = float(v)
        dps.append(dp)
    if kind == "sum":
        return {"name": name, "unit": unit,
                "sum": {"dataPoints": dps, "aggregationTemporality": 2, "isMonotonic": False}}
    return {"name": name, "unit": unit, "gauge": {"dataPoints": dps}}


def build_metrics(metrics, resource=None):
    res = dict(resource or {})
    res.setdefault("service.name", "galardo")
    return {"resourceMetrics": [{
        "resource": {"attributes": _attrs(res)},
        "scopeMetrics": [{"scope": {"name": SCOPE}, "metrics": list(metrics)}]}]}


def build_span(name, start_ns, end_ns, attrs=None, resource=None):
    res = dict(resource or {})
    res.setdefault("service.name", "galardo")
    return {"resourceSpans": [{
        "resource": {"attributes": _attrs(res)},
        "scopeSpans": [{"scope": {"name": SCOPE}, "spans": [{
            "name": name, "startTimeUnixNano": str(start_ns),
            "endTimeUnixNano": str(end_ns), "kind": 1,
            "attributes": _attrs(attrs)}]}]}]}


def _post(path, payload, url, timeout, sender):
    body = json.dumps(payload).encode("utf-8")
    if sender:
        try:
            sender(url.rstrip("/") + path, body, timeout)
            return True, "sent"
        except Exception as exc:
            return False, "%s: %s" % (type(exc).__name__, exc)
    try:
        import netssl
        ctx = netssl.context()
    except Exception:
        ctx = None
    req = urllib.request.Request(url.rstrip("/") + path, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return (200 <= r.status < 300), "http=%s" % r.status
    except urllib.error.HTTPError as exc:
        return False, "http=%s" % exc.code
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)


def send(payload, path="/v1/metrics", url=None, timeout=6.0, sender=None):
    """(ok, info). Tidak pernah melempar."""
    if not enabled() and url is None and sender is None:
        STATS["skipped"] += 1
        return False, "otlp nonaktif"
    u = url or os.environ.get("GALARDO_OTLP_URL") or "http://127.0.0.1:4318"
    ok, info = _post(path, payload, u, timeout, sender)
    with _LOCK:
        STATS["exported" if ok else "failed"] += 1
        if not ok:
            STATS["last_error"] = info
    return ok, info


def window_metrics(window, job_id=None, ts_ns=None):
    """Ubah hasil TelemetryRing.window() menjadi daftar metric OTLP."""
    attrs = {"job_id": job_id} if job_id else {}
    out = []
    for k, v in sorted((window or {}).items()):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(metric("galardo." + k, [{"value": v, "attrs": attrs, "ts_ns": ts_ns}]))
    return out


def export_job(job_id, window, started_ns=None, ended_ns=None, extra=None, sender=None):
    """Kirim metrics + satu span untuk satu job. Fail-open."""
    ms = window_metrics(window, job_id=job_id)
    ok1, i1 = send(build_metrics(ms, resource={"job.id": job_id}), "/v1/metrics", sender=sender)
    attrs = dict({"job.id": job_id}, **(extra or {}))
    ok2, i2 = send(build_span("job.run", started_ns or now_ns(), ended_ns or now_ns(), attrs),
                   "/v1/traces", sender=sender)
    return (ok1 and ok2), (i1 if not ok1 else i2)


def stats():
    return dict(STATS)
