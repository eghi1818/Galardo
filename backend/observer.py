"""Third-party observer via check-host.net - upgrades DOWN from LOKAL to GLOBAL.

A local probe can only prove "from my machine, this is down". To claim the
target is globally down you need nodes you do not control. This module asks
check-host.net to probe the URL from many countries and summarises the result.

Verdict is deliberately conservative: fewer than 20% of answering nodes OK is
GLOBAL_DOWN, under 60% is GLOBAL_PARTIAL, above that is GLOBAL_UP. Nodes that
never answer are excluded from the ratio and reported separately.

Python 3.9 compatible.
"""

from __future__ import annotations

import http.client
import json
import ssl
import time
from urllib.parse import quote, urlsplit

try:
    from . import external_probe as ep
except ImportError:
    import external_probe as ep

try:
    from .util import now_iso
except ImportError:
    from util import now_iso

__all__ = ["ObserverError", "ObserverCheck", "ObserverReport", "ObserverClient",
           "verify_down", "VERDICT_GLOBAL_UP", "VERDICT_GLOBAL_PARTIAL",
           "VERDICT_GLOBAL_DOWN", "VERDICT_UNKNOWN"]

VERDICT_GLOBAL_UP = "GLOBAL_UP"
VERDICT_GLOBAL_PARTIAL = "GLOBAL_PARTIAL"
VERDICT_GLOBAL_DOWN = "GLOBAL_DOWN"
VERDICT_UNKNOWN = "UNKNOWN"

OBSERVER_HOST = "check-host.net"
USER_AGENT = "Galardo/1.0 (+observer; out-of-band global down verification)"


class ObserverError(Exception):
    """The observer could not be reached or refused the request."""


class ObserverCheck(object):
    __slots__ = ("request_id", "permanent_link", "nodes", "kind", "target",
                 "started_at", "tls_mode", "encoding_mode")

    def __init__(self, request_id, permanent_link, nodes, kind, target):
        self.request_id = request_id
        self.permanent_link = permanent_link
        self.nodes = list(nodes or [])
        self.kind = kind
        self.target = target
        self.started_at = now_iso()
        self.tls_mode = None
        self.encoding_mode = None

    def to_dict(self):
        return {"request_id": self.request_id, "permanent_link": self.permanent_link,
                "node_count": len(self.nodes), "kind": self.kind,
                "target": self.target, "started_at": self.started_at}


class ObserverReport(object):
    """Parsed observer outcome. Pending nodes are counted, never guessed."""

    def __init__(self, check, raw):
        self.check = check
        self.raw = raw or {}
        self.nodes = {}
        for node, entries in (self.raw.get("nodes") or {}).items():
            if isinstance(entries, list):
                entry = entries[0] if entries else None
            else:
                entry = entries
            if entry is None:
                self.nodes[node] = {"ok": None, "pending": True}
                continue
            if isinstance(entry, dict):
                error = entry.get("error")
                self.nodes[node] = {"ok": error is None, "error": error,
                                    "time": entry.get("time"),
                                    "status": entry.get("status")}
            else:
                self.nodes[node] = {"ok": False, "error": str(entry)}

    @property
    def nodes_total(self):
        return len(self.nodes)

    @property
    def nodes_answered(self):
        return len([n for n in self.nodes.values() if n.get("ok") is not None])

    @property
    def nodes_failed(self):
        return len([n for n in self.nodes.values() if n.get("ok") is False])

    @property
    def ok_ratio(self):
        answered = self.nodes_answered
        if not answered:
            return 0.0
        return (answered - self.nodes_failed) / float(answered)

    @property
    def verdict(self):
        if not self.nodes_answered:
            return VERDICT_UNKNOWN
        ratio = self.ok_ratio
        if ratio <= 0.2:
            return VERDICT_GLOBAL_DOWN
        if ratio <= 0.6:
            return VERDICT_GLOBAL_PARTIAL
        return VERDICT_GLOBAL_UP

    def to_dict(self):
        return {"verdict": self.verdict, "ok_ratio": round(self.ok_ratio, 3),
                "nodes_total": self.nodes_total, "nodes_answered": self.nodes_answered,
                "nodes_failed": self.nodes_failed,
                "permanent_link": self.check.permanent_link,
                "kind": self.check.kind, "target": self.check.target,
                "nodes": self.nodes, "observed_at": now_iso(),
                "observer_tls_mode": getattr(self.check, "tls_mode", None),
                "observer_encoding_mode": getattr(self.check, "encoding_mode", None)}

    def __repr__(self):
        return "<ObserverReport %s ratio=%.2f answered=%d/%d>" % (
            self.verdict, self.ok_ratio, self.nodes_answered, self.nodes_total)


class ObserverClient(object):
    """Minimal check-host.net client. No dependencies beyond http.client.

    check-host.net is picky about how the target is percent-encoded and the
    accepted form has changed between deployments. Rather than guessing, try
    each known form until one actually returns nodes, then RECORD which worked.
    A 200 response with zero nodes is a failure, not a success.
    """

    ENCODERS = (
        ("safe=/: ", lambda value: quote(value, safe="/:")),
        ("safe=all", lambda value: quote(value, safe="")),
        ("raw", lambda value: value),
    )

    def __init__(self, host=OBSERVER_HOST, timeout=20.0, verify_tls=True):
        self.host = host
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.tls_mode = None
        self.encoding_mode = None

    def _get(self, path):
        """GET with a verified-first TLS policy.

        Some Python builds (notably macOS CommandLineTools 3.9) carry an empty
        or stale trust store, so the observer's chain fails verification. We
        try verified first, then fall back, and RECORD which mode was used.
        """
        attempts = []
        if self.verify_tls:
            attempts.append(("verified", ssl.create_default_context()))
        attempts.append(("unverified", ssl._create_unverified_context()))
        errors = []
        for label, context in attempts:
            conn = None
            try:
                conn = http.client.HTTPSConnection(self.host, timeout=self.timeout,
                                                   context=context)
                conn.request("GET", path, headers={
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                })
                resp = conn.getresponse()
                raw = resp.read()
                if resp.status != 200:
                    raise ObserverError("%s -> HTTP %d %s" % (path, resp.status, raw[:140]))
                self.tls_mode = label
                return json.loads(raw.decode("utf-8", "replace"))
            except ObserverError:
                raise
            except Exception as exc:
                errors.append("%s/%s: %s" % (label, type(exc).__name__, exc))
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
        raise ObserverError("%s -> %s" % (path, " | ".join(errors)))

    def start(self, url, max_nodes=10, kind="http", timeout=10, cache_buster=True):
        target = url
        endpoint = "check-tcp" if kind == "tcp" else "check-http"
        if kind == "tcp":
            parts = urlsplit(url)
            port = parts.port or (443 if parts.scheme == "https" else 80)
            target = "%s:%d" % (parts.hostname, port)
        elif cache_buster:
            parts = urlsplit(url)
            busted = ep.cache_buster_path(parts.path or "/")
            target = "%s://%s%s" % (parts.scheme, parts.netloc, busted)
            if parts.query:
                target += "&" + parts.query

        problems = []
        for label, encoder in self.ENCODERS:
            path = "/%s?host=%s&max_nodes=%d&timeout=%d" % (
                endpoint, encoder(target), int(max_nodes), int(timeout))
            try:
                doc = self._get(path)
            except ObserverError as exc:
                problems.append("%s: %s" % (label.strip(), str(exc)[:110]))
                continue
            if doc.get("ok") != 1:
                problems.append("%s: refused %s" % (label.strip(), json.dumps(doc)[:110]))
                continue
            nodes = list((doc.get("nodes") or {}).keys())
            if not nodes:
                problems.append("%s: HTTP 200 but 0 nodes" % label.strip())
                continue
            self.encoding_mode = label.strip()
            check = ObserverCheck(doc.get("request_id"), doc.get("permanent_link"),
                                  nodes, kind, target)
            check.tls_mode = self.tls_mode
            check.encoding_mode = self.encoding_mode
            return check
        raise ObserverError("no encoding produced nodes for %s (%s)" % (
            target, " | ".join(problems)))

    def result(self, request_id):
        return self._get("/check-result/" + request_id)

    def poll(self, check, timeout=30.0, interval=2.0):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            last = self.result(check.request_id)
            nodes = (last or {}).get("nodes") or {}
            if nodes and all(v is not None for v in nodes.values()):
                break
            time.sleep(interval)
        return ObserverReport(check, last or {})


def verify_down(url, max_nodes=10, kind="http", start_timeout=10,
                poll_timeout=30.0, interval=2.0, client=None):
    """Start a check and poll it to completion. Returns an ObserverReport.

    Raises ObserverError if the observer itself is unreachable - the caller
    must distinguish "observer down" from "target down".
    """
    client = client or ObserverClient()
    check = client.start(url, max_nodes=max_nodes, kind=kind, timeout=start_timeout)
    return client.poll(check, timeout=poll_timeout, interval=interval)


def escalate(local_verdict, url, min_local_state="DOWN", **kwargs):
    """Only ask the third party once the LOCAL probe already says DOWN.

    Saves observer quota and keeps the causal order honest: local evidence
    first, global confirmation second.
    """
    state = (local_verdict or {}).get("state")
    if min_local_state and state != min_local_state and state != "RECOVERING":
        return {"skipped": True, "reason": "local state %s < %s" % (state, min_local_state)}
    try:
        report = verify_down(url, **kwargs)
    except ObserverError as exc:
        return {"skipped": False, "error": str(exc), "verdict": VERDICT_UNKNOWN}
    out = report.to_dict()
    out["skipped"] = False
    return out
