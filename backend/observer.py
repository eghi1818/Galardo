"""GALARDO - Third-party observer via check-host.net (scope GLOBAL).

Purpose: prove a target is DOWN from OUTSIDE our own network, so the verdict
is not an artefact of our egress path. Used only when the local probe already
says DOWN (escalation), per the GOAL 2 design.

Three real-world traps encoded as features (all were live bugs):
  1. TLS: check-host occasionally presents a broken chain -> try verified
     first, fall back to unverified, and RECORD which mode was used.
  2. URL encoding: fully percent-encoded host is rejected (0 nodes) -> try
     encoder variants and RECORD which one worked.
  3. Result shape: the node map comes back FLAT with positional-list entries
     -> detect that shape and parse positionally, else every healthy node
     would be scored FAILED (false GLOBAL_DOWN).
"""
import json
import ssl
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import quote

try:
    from . import netssl as _ns
except ImportError:
    import netssl as _ns

BASE = "https://check-host.net"
START_PATH = "/check-http"
RESULT_PATH = "/check-result/"

META_KEYS = {"ok", "request_id", "permanent_link", "nodes", "error", "message"}
ENCODERS = (("safe=/:~", "/:~"), ("safe=all", ""), ("raw", None))

VERDICT_UP = "GLOBAL_UP"
VERDICT_PARTIAL = "GLOBAL_PARTIAL"
VERDICT_DOWN = "GLOBAL_DOWN"
VERDICT_UNKNOWN = "UNKNOWN"

DEFAULT_MAX_NODES = 8
ESCALATED_MAX_NODES = 24


def _enc(host, safe):
    return host if safe is None else quote(host, safe=safe)


def _int(v):
    try:
        return int(str(v).strip())
    except Exception:
        return None


def _float(v):
    try:
        return float(v)
    except Exception:
        return None


def _status_ok(status):
    n = _int(status)
    return n is not None and 200 <= n < 400


@dataclass
class ObserverCheck:
    node: str
    ok: bool
    status: Optional[int] = None
    latency_s: Optional[float] = None
    ip: Optional[str] = None
    error: Optional[str] = None
    raw: Any = None


@dataclass
class ObserverReport:
    check_id: Optional[str]
    url: str
    verdict: str
    ratio: float
    nodes_total: int
    nodes_ok: int
    nodes: List[ObserverCheck] = field(default_factory=list)
    tls_mode: Optional[str] = None
    encoding_mode: Optional[str] = None
    permanent_link: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            "source": "check-host.net",
            "scope": "GLOBAL",
            "check_id": self.check_id,
            "url": self.url,
            "verdict": self.verdict,
            "ratio": self.ratio,
            "nodes_total": self.nodes_total,
            "nodes_ok": self.nodes_ok,
            "nodes_requested": self.nodes_total,
            "nodes_answered": self.nodes_ok,
            "nodes": [asdict(c) for c in self.nodes],
            "tls_mode": self.tls_mode,
            "encoding_mode": self.encoding_mode,
            "permanent_link": self.permanent_link,
            "error": self.error,
        }

    def proves_global_down(self):
        return self.verdict == VERDICT_DOWN

    def proves_global_up(self):
        return self.verdict == VERDICT_UP


class ObserverClient:
    """Minimal, tolerant client. Never raises out of verify_down/escalate."""

    def __init__(self, tls_verify=True, max_nodes=DEFAULT_MAX_NODES, timeout=12.0):
        self.tls_verify = bool(tls_verify)
        self.max_nodes = int(max_nodes)
        self.timeout = float(timeout)
        self.tls_mode = None
        self.tls_fallback_reason = None
        self.encoding_mode = None
        self.last_error = None

    # ------------------------------------------------------------------
    def _get(self, url, timeout):
        last = None
        attempts = [("verified", _ns.context())]
        if True:
            attempts.append(("unverified", _ns.context(verify=False)))
        for mode, ctx in attempts:
            try:
                opener = urlrequest.build_opener(urlrequest.HTTPSHandler(context=ctx))
                req = urlrequest.Request(url, headers={
                    "Accept": "application/json",
                    "User-Agent": "GalardoObserver/1.0"})
                with opener.open(req, timeout=timeout) as resp:
                    body = resp.read().decode("utf-8", "replace")
                self.tls_mode = mode
                return json.loads(body)
            except Exception as e:
                last = e
                if mode == "verified":
                    self.tls_fallback_reason = str(e)[:200]
        raise last

    def start(self, url, max_nodes=None, timeout=None):
        """Create a check. Tries encoding variants until nodes appear."""
        self.last_error = None
        max_nodes = max_nodes or self.max_nodes
        timeout = timeout or self.timeout
        host = url
        for name, safe in ENCODERS:
            try:
                qs = "?host=%s&max_nodes=%d&timeout=%d" % (_enc(host, safe), max_nodes, int(timeout))
                doc = self._get(BASE + START_PATH + qs, timeout)
            except Exception as e:
                self.last_error = "start(%s) failed: %s" % (name, e)
                continue
            nodes = doc.get("nodes") or {}
            if nodes:
                self.encoding_mode = name
                return doc
            self.last_error = "encoder %s returned 0 nodes" % name
        return None

    @staticmethod
    def _parse_entry(node, entry):
        if entry is None:
            return ObserverCheck(node=node, ok=False, error="no data from node", raw=entry)
        if isinstance(entry, dict):
            status = entry.get("status") or entry.get("code")
            err = entry.get("error")
            ok = _status_ok(status) and not err
            return ObserverCheck(node=node, ok=ok, status=_int(status),
                                 latency_s=_float(entry.get("time") or entry.get("seconds")),
                                 ip=entry.get("ip"), error=err, raw=entry)
        if isinstance(entry, (list, tuple)):
            # positional shape: [flag, seconds, label, status, ip]
            status = entry[3] if len(entry) > 3 else None
            label = entry[2] if len(entry) > 2 else None
            ok = _status_ok(status)
            return ObserverCheck(node=node, ok=ok, status=_int(status),
                                 latency_s=_float(entry[1] if len(entry) > 1 else None),
                                 ip=entry[4] if len(entry) > 4 else None,
                                 error=None if ok else str(label or status or "failed"),
                                 raw=list(entry))
        return ObserverCheck(node=node, ok=False, error="unparsable entry", raw=entry)

    def result(self, check_id, timeout=None):
        """Fetch per-node results. Handles BOTH nested and flat node maps."""
        doc = self._get(BASE + RESULT_PATH + quote(str(check_id)), timeout or self.timeout)
        raw_nodes = doc.get("nodes")
        if isinstance(raw_nodes, dict) and raw_nodes:
            nodes_map = raw_nodes
        else:
            nodes_map = {k: v for k, v in doc.items() if k not in META_KEYS}
        return [self._parse_entry(n, e) for n, e in nodes_map.items()]

    # ------------------------------------------------------------------
    def _report(self, url, max_nodes, timeout, poll_timeout=None):
        doc = self.start(url, max_nodes=max_nodes, timeout=timeout)
        if not doc:
            return ObserverReport(None, url, VERDICT_UNKNOWN, 0.0, 0, 0, [],
                                  self.tls_mode, self.encoding_mode, None, self.last_error)
        cid = doc.get("request_id")
        deadline = time.time() + float(poll_timeout or 20.0)
        checks, last_err = [], None
        while True:
            time.sleep(1.0)
            try:
                checks = self.result(cid, timeout=timeout)
                last_err = None
            except Exception as e:
                checks, last_err = [], str(e)
            if any(c.raw is not None for c in checks):
                break
            if time.time() >= deadline:
                break
        if not checks and last_err:
            return ObserverReport(cid, url, VERDICT_UNKNOWN, 0.0, 0, 0, [],
                                  self.tls_mode, self.encoding_mode,
                                  doc.get("permanent_link"), "result failed: %s" % last_err)
        total = len(checks)
        ok = sum(1 for c in checks if c.ok)
        ratio = (ok / total) if total else 0.0
        if total == 0:
            verdict = VERDICT_UNKNOWN
        elif ok == 0:
            verdict = VERDICT_DOWN
        elif ok == total:
            verdict = VERDICT_UP
        else:
            verdict = VERDICT_PARTIAL
        return ObserverReport(cid, url, verdict, round(ratio, 4), total, ok, checks,
                              self.tls_mode, self.encoding_mode,
                              doc.get("permanent_link"), None)

    def verify_down(self, url, max_nodes=None, timeout=None, poll_timeout=None):
        return self._report(url, max_nodes or self.max_nodes, timeout or self.timeout,
                            poll_timeout=poll_timeout)

    def escalate(self, url, max_nodes=ESCALATED_MAX_NODES, timeout=None, poll_timeout=None):
        """Wider node fan-out when a DOWN verdict needs stronger proof."""
        return self._report(url, max_nodes, timeout or (self.timeout + 3),
                            poll_timeout=poll_timeout)


_DEFAULT = None


def client():
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ObserverClient()
    return _DEFAULT


def _flex(verdict, url, max_nodes, timeout, wider, poll_timeout=None):
    """Accepts both (verdict, url) and legacy (url) call shapes."""
    if url is None and isinstance(verdict, str):
        url, verdict = verdict, None
    if url is None:
        raise ValueError("observer: url is required")
    cl = client()
    rep = (cl.escalate(url, max_nodes=max_nodes, timeout=timeout, poll_timeout=poll_timeout)
           if wider else
           cl.verify_down(url, max_nodes=max_nodes, timeout=timeout, poll_timeout=poll_timeout))
    d = rep.to_dict()
    if isinstance(verdict, dict):
        d["local_verdict"] = {"state": verdict.get("state"),
                              "down_verified": verdict.get("down_verified"),
                              "time_to_recover": verdict.get("time_to_recover")}
    return d


def verify_down(verdict=None, url=None, max_nodes=DEFAULT_MAX_NODES, timeout=12.0, **kw):
    return _flex(verdict, url, max_nodes, timeout, False, kw.get("poll_timeout"))


def escalate(verdict=None, url=None, max_nodes=ESCALATED_MAX_NODES, timeout=15.0, **kw):
    return _flex(verdict, url, max_nodes, timeout, True, kw.get("poll_timeout"))
