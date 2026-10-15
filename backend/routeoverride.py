"""Force a chosen route to 404 / blank (Goal 3). Three tiers, stdlib only.

T2  local intercept shim   - answers 404/blank itself. No sudo. Process-local.
T1  /etc/hosts block       - machine-local. Needs T2 to be useful, because
                             hosts cannot carry a port: something must own
                             :80/:443 for the redirected hostname to answer.
T3  Cloudflare edge rule   - global, but only for zones you own, and it needs
                             an API token. Recorded as best-effort: Cloudflare
                             accepts a limited set of status codes on redirect
                             rules, so 404 is attempted first and 302 is used
                             as a fallback, and which one was used is RECORDED.

Every tier reports what it actually did, so evidence can distinguish
"forced locally" from "forced globally" instead of pretending.

Python 3.9 compatible.
"""

from __future__ import annotations

import fnmatch
import http.client
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

try:
    from . import transport as transport_mod
except ImportError:
    import transport as transport_mod

try:
    from .util import now_iso
except ImportError:
    from util import now_iso

__all__ = [
    "OverrideError", "OverrideSpec", "TierResult", "LocalShim", "HostsOverride",
    "CloudflareEdgeOverride", "CertAuthority", "RouteOverrider",
    "MODES", "HOSTS_MARK_BEGIN", "HOSTS_MARK_END",
]

MODES = {"404": 404, "410": 410, "503": 503, "blank": 200}
HOSTS_PATH = "/etc/hosts"
HOSTS_MARK_BEGIN = "# >>> galardo route override >>>"
HOSTS_MARK_END = "# <<< galardo route override <<<"
CF_API_HOST = "api.cloudflare.com"
CF_PHASE = "http_request_dynamic_redirect"


class OverrideError(Exception):
    """A tier could not be applied; the caller decides whether to continue."""


class OverrideSpec(object):
    """What to force. ``paths`` are glob patterns matched against the URL path."""

    def __init__(self, domain, paths=None, mode="404", hosts=None, note="", ttl_seconds=None):
        self.domain = str(domain).strip().lower().strip(".")
        self.paths = list(paths or ["/*"])
        self.mode = mode if mode in MODES else "404"
        self.hosts = list(hosts or [self.domain])
        self.note = note
        self.ttl_seconds = ttl_seconds
        self.created_at = now_iso()

    def matches(self, path):
        path = path or "/"
        for pattern in self.paths:
            if fnmatch.fnmatch(path, pattern):
                return True
            if pattern.endswith("*") and path.startswith(pattern[:-1]):
                return True
        return False

    @property
    def status_code(self):
        return MODES[self.mode]

    @property
    def is_blank(self):
        return self.mode == "blank"

    def to_dict(self):
        return {"domain": self.domain, "paths": self.paths, "mode": self.mode,
                "hosts": self.hosts, "note": self.note,
                "ttl_seconds": self.ttl_seconds, "created_at": self.created_at}


class TierResult(object):
    def __init__(self, tier, ok, detail, data=None):
        self.tier = tier
        self.ok = bool(ok)
        self.detail = detail
        self.data = data or {}
        self.at = now_iso()

    def to_dict(self):
        return {"tier": self.tier, "ok": self.ok, "detail": self.detail,
                "data": self.data, "at": self.at}

    def __repr__(self):
        return "<TierResult %s ok=%s %s>" % (self.tier, self.ok, self.detail)


# --------------------------------------------------------------------------
# T2 - local intercept shim
# --------------------------------------------------------------------------
class _ShimHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "GalardoShim/1.0"

    def log_message(self, fmt, *args):
        pass

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else None

    def _respond(self, code, body, content_type="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _handle(self):
        shim = self.server.shim
        parts = urlsplit(self.path)
        path = parts.path or "/"
        payload = self._read_body() if self.command in ("POST", "PUT", "PATCH") else None

        if shim.spec.matches(path):
            shim.note_hit(path, self.command)
            if shim.spec.is_blank:
                return self._respond(200, b"", "text/plain",
                                     {"X-Galardo-Override": "blank", "Cache-Control": "no-store"})
            body = json.dumps({"galardo": "forced", "mode": shim.spec.mode,
                               "path": path, "method": self.command}).encode("utf-8")
            return self._respond(shim.spec.status_code, body, "application/json",
                                 {"X-Galardo-Override": shim.spec.mode,
                                  "Cache-Control": "no-store"})

        if not shim.upstream:
            return self._respond(404, b'{"galardo":"shim:no-upstream"}', "application/json")
        shim.note_pass(path, self.command)
        url = shim.upstream.rstrip("/") + self.path
        headers = {"Accept": self.headers.get("Accept") or "*/*"}
        for key in ("Content-Type", "Accept-Encoding"):
            if self.headers.get(key):
                headers[key] = self.headers.get(key)
        try:
            resp = shim.transport.request(self.command, url, headers=headers, body=payload,
                                          timeout=shim.timeout, connect_ip=shim.connect_ip)
        except Exception as exc:
            return self._respond(502, json.dumps({"galardo": "shim upstream error",
                                                  "detail": str(exc)[:160]}).encode(),
                                 "application/json")
        if resp.error:
            return self._respond(502, json.dumps({"galardo": "shim upstream error",
                                                  "detail": resp.error[:160]}).encode(),
                                 "application/json")
        return self._respond(resp.status or 502, resp.body or b"",
                             resp.header("content-type") or "application/octet-stream")

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_PATCH = _handle
    do_DELETE = _handle
    do_HEAD = _handle


class LocalShim(object):
    """T2: an HTTP server that forces matched paths and forwards the rest."""

    def __init__(self, spec, upstream=None, port=8899, host="127.0.0.1",
                 connect_ip=None, timeout=10.0):
        self.spec = spec
        self.upstream = upstream
        self.host = host
        self.port = port
        self.connect_ip = connect_ip
        self.timeout = timeout
        self.transport = transport_mod.Transport(timeout=timeout, max_idle=8)
        self.httpd = None
        self.thread = None
        self.hits = []
        self.passes = []
        self.lock = threading.Lock()

    def note_hit(self, path, method):
        with self.lock:
            self.hits.append({"at": now_iso(), "path": path, "method": method})
            self.hits[:] = self.hits[-500:]

    def note_pass(self, path, method):
        with self.lock:
            self.passes.append({"at": now_iso(), "path": path, "method": method})
            self.passes[:] = self.passes[-500:]

    def start(self):
        self.httpd = ThreadingHTTPServer((self.host, self.port), _ShimHandler)
        self.httpd.shim = self
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       daemon=True, name="galardo-shim")
        self.thread.start()
        return self

    def stop(self):
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        try:
            self.transport.close()
        except Exception:
            pass

    def proxy_tuple(self):
        return (self.host, self.port)

    def url_for(self, path="/"):
        return "http://%s:%d%s" % (self.host, self.port, path)

    def stats(self):
        with self.lock:
            return {"forced": len(self.hits), "passed": len(self.passes),
                    "port": self.port, "mode": self.spec.mode}


# --------------------------------------------------------------------------
# T1 - /etc/hosts
# --------------------------------------------------------------------------
class HostsOverride(object):
    """T1: point the hostname at an address. Needs sudo for /etc/hosts."""

    def __init__(self, path=HOSTS_PATH):
        self.path = path
        self.applied = None

    def _read(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            return handle.read()

    def current_block(self):
        try:
            text = self._read()
        except OSError:
            return None
        if HOSTS_MARK_BEGIN not in text:
            return None
        after = text.split(HOSTS_MARK_BEGIN, 1)[1]
        return after.split(HOSTS_MARK_END, 1)[0].strip()

    def _strip_block(self, text):
        lines = text.splitlines()
        out, inside = [], False
        for line in lines:
            if line.strip() == HOSTS_MARK_BEGIN:
                inside = True
                continue
            if line.strip() == HOSTS_MARK_END:
                inside = False
                continue
            if not inside:
                out.append(line)
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out) + "\n"

    def _sudo_write(self, content):
        handle, temp_path = tempfile.mkstemp(prefix="galardo-hosts-")
        os.close(handle)
        with open(temp_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        try:
            subprocess.run(["sudo", "cp", temp_path, self.path], check=True)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def apply(self, hosts, address="127.0.0.1"):
        block = [HOSTS_MARK_BEGIN]
        for host in hosts:
            block.append("%-15s %s" % (address, host))
        block.append(HOSTS_MARK_END)
        try:
            text = self._strip_block(self._read())
        except OSError as exc:
            raise OverrideError("cannot read %s: %s" % (self.path, exc))
        content = text.rstrip("\n") + "\n\n" + "\n".join(block) + "\n"
        try:
            self._sudo_write(content)
        except Exception as exc:
            raise OverrideError("sudo write failed: %s" % exc)
        self.applied = {"hosts": list(hosts), "address": address, "at": now_iso()}
        self.flush_cache()
        return self.applied

    def revert(self):
        try:
            text = self._strip_block(self._read())
        except OSError as exc:
            raise OverrideError("cannot read %s: %s" % (self.path, exc))
        self._sudo_write(text)
        self.applied = None
        self.flush_cache()
        return True

    @staticmethod
    def flush_cache():
        for cmd in (["sudo", "dscacheutil", "-flushcache"],
                    ["sudo", "killall", "-HUP", "mDNSResponder"]):
            try:
                subprocess.run(cmd, check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def status(self):
        return {"applied": self.applied, "block": self.current_block(),
                "path": self.path}


# --------------------------------------------------------------------------
# T3 - Cloudflare edge rule (best effort)
# --------------------------------------------------------------------------
class CloudflareEdgeOverride(object):
    """T3: a dynamic-redirect rule at the Cloudflare edge. Needs a token."""

    def __init__(self, token=None, timeout=20.0):
        self.token = token or os.environ.get("GALARDO_CF_TOKEN") or ""
        self.timeout = timeout
        self.applied = None

    @property
    def configured(self):
        return bool(self.token)

    def _request(self, method, path, body=None):
        if not self.token:
            raise OverrideError("GALARDO_CF_TOKEN not set")
        conn = None
        try:
            conn = http.client.HTTPSConnection(CF_API_HOST, timeout=self.timeout)
            payload = json.dumps(body).encode("utf-8") if body is not None else None
            headers = {"Authorization": "Bearer " + self.token,
                       "Content-Type": "application/json",
                       "User-Agent": "Galardo/1.0 (+routeoverride)"}
            conn.request(method, "/client/v4" + path, body=payload, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            doc = json.loads(raw.decode("utf-8", "replace") or "{}")
            if not doc.get("success", False):
                errors = doc.get("errors") or []
                raise OverrideError("cloudflare %s %s: %s" % (
                    method, path, json.dumps(errors)[:200]))
            return doc.get("result")
        except OverrideError:
            raise
        except Exception as exc:
            raise OverrideError("cloudflare transport: %s: %s" % (type(exc).__name__, exc))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def zone_id(self, domain):
        labels = domain.split(".")
        for cut in range(0, max(0, len(labels) - 1)):
            candidate = ".".join(labels[cut:])
            result = self._request("GET", "/zones?name=" + candidate)
            if result:
                return result[0]["id"], candidate
        raise OverrideError("no Cloudflare zone found for %s" % domain)

    def _ruleset_path(self, zone):
        return "/zones/%s/rulesets/phases/%s/entrypoint" % (zone, CF_PHASE)

    def _description(self, spec):
        return "galardo-forced-%s-%s" % (spec.mode, spec.domain)

    def _expression(self, spec):
        host = '(http.host eq "%s")' % spec.domain
        if spec.paths == ["/*"]:
            return host
        clauses = []
        for pattern in spec.paths:
            if pattern.endswith("*"):
                clauses.append('starts_with(http.request.uri.path, "%s")' % pattern[:-1])
            else:
                clauses.append('(http.request.uri.path eq "%s")' % pattern)
        return "(%s and (%s))" % (host, " or ".join(clauses))

    def _rule(self, spec, status_code):
        return {
            "description": self._description(spec),
            "expression": self._expression(spec),
            "action": "redirect",
            "action_parameters": {
                "from_value": {
                    "status_code": status_code,
                    "target_url": {"expression": 'concat("https://", http.host, http.request.uri.path)'},
                    "preserve_query_string": True,
                }
            },
            "enabled": True,
        }

    def apply(self, spec, status_codes=(404, 302)):
        if not self.configured:
            raise OverrideError("GALARDO_CF_TOKEN not set - T3 skipped")
        zone, zone_name = self.zone_id(spec.domain)
        existing = None
        try:
            existing = self._request("GET", self._ruleset_path(zone))
        except OverrideError:
            existing = None
        base = [r for r in ((existing or {}).get("rules") or [])
                if r.get("description") != self._description(spec)]

        last_error = None
        for code in status_codes:
            rules = base + [self._rule(spec, code)]
            try:
                self._request("PUT", self._ruleset_path(zone),
                              {"rules": rules, "name": "Galardo route override",
                               "kind": "zone", "phase": CF_PHASE})
                self.applied = {"zone_id": zone, "zone_name": zone_name,
                                "status_code": code, "expression": self._expression(spec),
                                "at": now_iso()}
                return self.applied
            except OverrideError as exc:
                last_error = exc
        raise OverrideError("ruleset PUT failed for every status code: %s" % last_error)

    def revert(self, spec):
        if not self.configured:
            raise OverrideError("GALARDO_CF_TOKEN not set")
        zone, _ = self.zone_id(spec.domain)
        try:
            existing = self._request("GET", self._ruleset_path(zone))
        except OverrideError:
            return {"removed": 0}
        rules = [r for r in ((existing or {}).get("rules") or [])
                 if r.get("description") != self._description(spec)]
        removed = len(((existing or {}).get("rules") or [])) - len(rules)
        if removed:
            self._request("PUT", self._ruleset_path(zone),
                          {"rules": rules, "name": "Galardo route override",
                           "kind": "zone", "phase": CF_PHASE})
        self.applied = None
        return {"removed": removed, "zone_id": zone}


# --------------------------------------------------------------------------
# optional: local certificate authority for an HTTPS shim
# --------------------------------------------------------------------------
class CertAuthority(object):
    """Self-signed cert via openssl, for intercepting HTTPS locally."""

    def __init__(self, directory=None):
        self.directory = directory or tempfile.mkdtemp(prefix="galardo-ca-")
        self.key_path = os.path.join(self.directory, "key.pem")
        self.cert_path = os.path.join(self.directory, "cert.pem")

    @property
    def available(self):
        return shutil.which("openssl") is not None

    def issue(self, domain):
        if not self.available:
            raise OverrideError("openssl not found")
        cmd = ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
               "-keyout", self.key_path, "-out", self.cert_path, "-days", "30",
               "-subj", "/CN=" + domain,
               "-addext", "subjectAltName=DNS:" + domain]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            raise OverrideError("openssl failed: %s" % exc)
        return {"cert": self.cert_path, "key": self.key_path, "domain": domain}


# --------------------------------------------------------------------------
# facade
# --------------------------------------------------------------------------
class RouteOverrider(object):
    """Applies the tiers you ask for and reports honestly what each one did."""

    def __init__(self, spec, upstream=None, connect_ip=None, shim_port=8899,
                 cf_token=None, shim_host="127.0.0.1"):
        self.spec = spec
        self.upstream = upstream
        self.connect_ip = connect_ip
        self.shim_port = shim_port
        self.shim_host = shim_host
        self.shim = None
        self.hosts = HostsOverride()
        self.edge = CloudflareEdgeOverride(token=cf_token)
        self.results = []

    def apply(self, tiers=("T2",)):
        self.results = []
        for tier in tiers:
            try:
                if tier == "T2":
                    self.shim = LocalShim(self.spec, upstream=self.upstream,
                                          port=self.shim_port, host=self.shim_host,
                                          connect_ip=self.connect_ip).start()
                    self.results.append(TierResult("T2", True,
                                                   "shim listening on %s" % self.shim.url_for("/"),
                                                   self.shim.stats()))
                elif tier == "T1":
                    data = self.hosts.apply(self.spec.hosts)
                    self.results.append(TierResult("T1", True,
                                                   "hosts block applied for %d host(s)" % len(self.spec.hosts),
                                                   data))
                elif tier == "T3":
                    data = self.edge.apply(self.spec)
                    self.results.append(TierResult(
                        "T3", True,
                        "edge rule applied (status_code=%s)" % data.get("status_code"), data))
                else:
                    self.results.append(TierResult(tier, False, "unknown tier"))
            except OverrideError as exc:
                self.results.append(TierResult(tier, False, str(exc)))
        return self.report()

    def revert(self, tiers=None):
        tiers = tiers or [r.tier for r in self.results if r.ok]
        for tier in tiers:
            try:
                if tier == "T2" and self.shim is not None:
                    self.shim.stop()
                    self.shim = None
                elif tier == "T1":
                    self.hosts.revert()
                elif tier == "T3":
                    self.edge.revert(self.spec)
            except OverrideError:
                pass
        return {"reverted": tiers}

    def report(self):
        ok = [r for r in self.results if r.ok]
        return {"spec": self.spec.to_dict(), "tiers": [r.to_dict() for r in self.results],
                "applied_tiers": [r.tier for r in ok],
                "failed_tiers": [r.tier for r in self.results if not r.ok],
                "global_scope": "T3" in [r.tier for r in ok],
                "at": now_iso()}

    def evidence(self):
        data = self.report()
        if self.shim is not None:
            data["shim"] = self.shim.stats()
            data["shim_url"] = self.shim.url_for("/")
        data["hosts_block"] = self.hosts.current_block()
        data["edge"] = self.edge.applied
        return data
