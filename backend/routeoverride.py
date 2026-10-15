"""GALARDO - GOAL 3: force a route to 404/410/503/blank on demand.

Three tiers, tried in order, first success wins, and EVERY attempt records
what actually happened (no silent degradation):

  T2 local-shim  : ThreadingHTTPServer on 127.0.0.1 that returns the forced
                   status for matched paths and proxies the rest. Proven tier.
  T1 hosts       : append "127.0.0.1 <host> # galardo-override" to /etc/hosts
                   so the REAL hostname resolves to the shim (needs sudo).
  T3 cf-worker   : deploy a Cloudflare Worker that answers the forced status
                   at the edge for the matched paths (needs a CF token).

The forced response ALWAYS carries header "X-Galardo-Override: <mode>".
That header is the discriminator: a bare 404 from a real upstream is
indistinguishable from a forced one without it.
"""
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, asdict, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, quote

OVERRIDE_HEADER = "X-Galardo-Override"

try:
    import envload
    envload.load()
except Exception:
    pass

MODES = {
    "404":   {"status": 404, "body": b"", "reason": "Not Found"},
    "410":   {"status": 410, "body": b"", "reason": "Gone"},
    "503":   {"status": 503, "body": b"", "reason": "Service Unavailable"},
    "blank": {"status": 200, "body": b"", "reason": "OK"},
}


class _NoRedirect(urlrequest.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@dataclass
class OverrideSpec:
    origin: str
    paths: List[str] = field(default_factory=lambda: ["/*"])
    mode: str = "404"
    spec_id: str = ""
    shim_port: Optional[int] = None
    tiers: Optional[List[str]] = None
    upstream: Optional[str] = None
    host_header: Optional[str] = None
    port: Optional[int] = None
    label: str = ""
    hosts: Optional[List[str]] = None  # compat-w7
    note: str = ""                     # compat-w7

    def __post_init__(self):
        if not self.spec_id:
            self.spec_id = "ov-%d" % int(time.time() * 1000)
        if self.port is None and self.shim_port is not None:
            self.port = int(self.shim_port)
        if isinstance(self.paths, str):
            self.paths = [self.paths]
        if self.mode not in MODES:
            raise ValueError("mode must be one of %s" % sorted(MODES))
        if not self.paths:
            raise ValueError("paths must not be empty")

    @property
    def id(self):
        return self.spec_id

    def host(self):
        return urlsplit(self.origin).hostname or self.origin

    def matches(self, path):
        """Wildcard-aware. "/blocked/*" cocok untuk /blocked, /blocked/, /blocked/x."""
        if not path.startswith("/"):
            path = "/" + path
        for p in self.paths:
            if p in ("*", "/*"):
                return True
            base = p.rstrip("*").rstrip("/")
            if not base:
                return True
            if path == base or path.startswith(base + "/"):
                return True
        return False

    def forced_status(self):
        return MODES[self.mode]["status"]

    def to_dict(self):
        return {"spec_id": self.spec_id, "origin": self.origin, "paths": list(self.paths),
                "mode": self.mode, "upstream": self.upstream, "host_header": self.host_header,
                "port": self.port, "label": self.label, "forced_status": self.forced_status()}


@dataclass
class TierResult:
    tier: str
    ok: bool
    detail: str = ""
    artifact: Optional[dict] = None
    status_code: Optional[int] = None


# ---------------------------------------------------------------------------
# T2 - local shim (proven)
# ---------------------------------------------------------------------------
class LocalShim:
    TIER = "T2-local-shim"

    def __init__(self, spec, port=None, upstream=None, connect_ip=None, **kw):
        self.spec = spec
        self.port = int(port) if port else (spec.port or _free_port())
        self.upstream = upstream or spec.upstream
        self.connect_ip = connect_ip
        self.host_header = spec.host_header or spec.host()
        self.httpd = None
        self.thread = None
        self.hits = 0
        self.forced_hits = 0

    def url(self):
        return "http://127.0.0.1:%d" % self.port

    def url_for(self, path="/"):
        if not path.startswith("/"):
            path = "/" + path
        return self.url() + path

    def start(self):
        spec = self.spec
        shim = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                self._serve("GET")

            def do_HEAD(self):
                self._serve("HEAD")

            def do_POST(self):
                self._serve("POST")

            def _serve(self, method):
                shim.hits += 1
                path = urlsplit(self.path).path
                if spec.matches(path):
                    shim.forced_hits += 1
                    m = MODES[spec.mode]
                    body = m["body"]
                    self.send_response(m["status"], m["reason"])
                    self.send_header(OVERRIDE_HEADER, spec.mode)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    if method != "HEAD" and body:
                        try:
                            self.wfile.write(body)
                        except (BrokenPipeError, ConnectionResetError):
                            pass
                    return

                if not shim.upstream:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                target = shim.upstream.rstrip("/") + self.path
                try:
                    req = urlrequest.Request(target, method=method)
                    req.add_header("User-Agent", "GalardoShim/1.0")
                    if shim.host_header:
                        req.add_header("Host", shim.host_header)
                    with urlrequest.build_opener().open(req, timeout=10) as resp:
                        data = resp.read()
                        code = resp.getcode()
                        ctype = resp.headers.get("Content-Type", "text/html; charset=utf-8")
                except HTTPError as e:
                    data = e.read()
                    code = e.code
                    ctype = "text/html; charset=utf-8"
                except Exception as e:
                    data = str(e)[:200].encode()
                    code = 502
                    ctype = "text/plain"
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if method != "HEAD" and data:
                    try:
                        self.wfile.write(data)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        except OSError:
            self.port = _free_port()
            self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True,
                                       name="galardo-shim-%d" % self.port)
        self.thread.start()
        time.sleep(0.15)
        return self

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        self.httpd = None

    def probe(self, path="/"):
        url = self.url() + path
        t0 = time.time()
        try:
            opener = urlrequest.build_opener(_NoRedirect())
            req = urlrequest.Request(url, headers={"User-Agent": "GalardoShimProbe/1.0"})
            with opener.open(req, timeout=5) as r:
                body = r.read()
                return {"status": r.getcode(), "override_header": r.headers.get(OVERRIDE_HEADER),
                        "body_len": len(body), "forced": bool(r.headers.get(OVERRIDE_HEADER)),
                        "latency_ms": round((time.time() - t0) * 1000, 2), "url": url}
        except HTTPError as e:
            body = e.read()
            return {"status": e.code, "override_header": e.headers.get(OVERRIDE_HEADER),
                    "body_len": len(body), "forced": bool(e.headers.get(OVERRIDE_HEADER)),
                    "latency_ms": round((time.time() - t0) * 1000, 2), "url": url}
        except Exception as e:
            return {"status": None, "error": str(e)[:200], "url": url}

    def stats(self):
        return {"tier": self.TIER, "port": self.port, "hits": self.hits,
                "forced_hits": self.forced_hits, "running": bool(self.httpd)}


# ---------------------------------------------------------------------------
# T1 - /etc/hosts
# ---------------------------------------------------------------------------
class HostsOverride:
    TIER = "T1-hosts"
    PATH = "/etc/hosts"
    MARK = "# galardo-override"

    def __init__(self, path=None, hosts=None, **kw):
        self.path = path or self.PATH

    def plan(self, host, ip="127.0.0.1"):
        return "%s\t%s\t%s" % (ip, host, self.MARK)

    def current(self, host):
        try:
            with open(self.path) as fh:
                return [l.rstrip("\n") for l in fh if host in l]
        except Exception as e:
            return ["<err %s>" % e]

    def apply(self, host, ip="127.0.0.1", use_sudo=True):
        line = self.plan(host, ip)
        try:
            with open(self.path) as fh:
                txt = fh.read()
        except Exception as e:
            return TierResult(self.TIER, False, "read %s failed: %s" % (self.path, e))
        if self.MARK in txt and ("\t%s\t" % host) in txt or (" %s " % host) in txt:
            return TierResult(self.TIER, True, "already present", {"line": line, "path": self.path})
        new = txt.rstrip("\n") + "\n" + line + "\n"
        tmp = "/tmp/galardo-hosts-%d" % os.getpid()
        try:
            with open(tmp, "w") as fh:
                fh.write(new)
        except Exception as e:
            return TierResult(self.TIER, False, "write tmp failed: %s" % e)
        manual = "sudo sh -c 'echo \"%s\" >> %s'" % (line, self.path)
        if use_sudo and not os.access(self.path, os.W_OK):
            p = subprocess.run(["sudo", "-n", "cp", tmp, self.path],
                               capture_output=True, text=True)
            if p.returncode != 0:
                return TierResult(self.TIER, False,
                                  "sudo cp failed (need sudo): %s" % ((p.stderr or p.stdout or "")[:200]),
                                  {"line": line, "manual": manual, "path": self.path})
        else:
            try:
                shutil.copyfile(tmp, self.path)
            except Exception as e:
                return TierResult(self.TIER, False, str(e)[:200], {"line": line, "manual": manual})
        return TierResult(self.TIER, True, "added to %s" % self.path,
                          {"line": line, "path": self.path})

    def revert(self, host=None):
        try:
            with open(self.path) as fh:
                lines = fh.read().split("\n")
        except Exception as e:
            return TierResult(self.TIER, False, "read failed: %s" % e)
        kept = [l for l in lines if not (self.MARK in l and (host is None or host in l))]
        tmp = "/tmp/galardo-hosts-rev-%d" % os.getpid()
        with open(tmp, "w") as fh:
            fh.write("\n".join(kept))
        if not os.access(self.path, os.W_OK):
            p = subprocess.run(["sudo", "-n", "cp", tmp, self.path], capture_output=True, text=True)
            if p.returncode != 0:
                return TierResult(self.TIER, False, "sudo cp failed", {"manual": "sudo cp %s %s" % (tmp, self.path)})
        else:
            shutil.copyfile(tmp, self.path)
        return TierResult(self.TIER, True, "override lines removed")


# ---------------------------------------------------------------------------
# T3 - Cloudflare edge override (Worker + route + proxied hostname)
#
# Ini tier yang membuat override terlihat dari INTERNET, bukan cuma lokal.
# Tiga langkah, semuanya dicatat status HTTP API-nya apa adanya:
#   1. pastikan hostname target punya DNS record PROXIED (orange cloud)
#   2. upload Worker (coba service-worker dulu, lalu modules multipart)
#   3. bind route "<host>/*" ke Worker itu
# Verifikasi dilakukan lewat HTTPS ke edge dengan retry (edge butuh beberapa detik).
#
# Token perlu izin: Account.Workers Scripts:Edit, Zone.Workers Routes:Edit,
# Zone.DNS:Edit (opsional Zone.Cache Purge).
# ---------------------------------------------------------------------------
CF_API = "https://api.cloudflare.com/client/v4"

WORKER_SOURCE = r"""// galardo edge override - generated
var PATHS = __PATHS__;
var STATUS = __STATUS__;
var MODE = __MODE__;
var BODY = __BODY__;

function galardoHit(pathname) {
  for (var i = 0; i < PATHS.length; i++) {
    var raw = PATHS[i];
    if (raw === "*" || raw === "/*") return true;
    var base = raw.replace(/\*+$/, "").replace(/\/+$/, "");
    if (base === "") return true;
    if (pathname === base) return true;
    if (pathname.indexOf(base + "/") === 0) return true;
  }
  return false;
}

addEventListener("fetch", function (event) {
  var url = new URL(event.request.url);
  if (!galardoHit(url.pathname)) {
    return event.respondWith(fetch(event.request));
  }
  return event.respondWith(new Response(BODY, {
    status: STATUS,
    headers: {
      "x-galardo-override": MODE,
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store"
    }
  }));
});
"""


def _multipart(metadata, files, boundary=None):
    """Build multipart/form-data for the Workers modules upload (stdlib only)."""
    boundary = boundary or ("----galardo%d" % int(time.time() * 1000))
    out = []
    out.append(("--" + boundary).encode())
    out.append(b'Content-Disposition: form-data; name="metadata"')
    out.append(b"Content-Type: application/json")
    out.append(b"")
    out.append(json.dumps(metadata).encode())
    for fname, content in files.items():
        out.append(("--" + boundary).encode())
        out.append(('Content-Disposition: form-data; name="%s"; filename="%s"'
                    % (fname, fname)).encode())
        out.append(b"Content-Type: application/javascript+module")
        out.append(b"")
        out.append(content.encode())
    out.append(("--" + boundary + "--").encode())
    out.append(b"")
    return b"\r\n".join(out), "multipart/form-data; boundary=" + boundary


def _edge_probe(url, timeout=10.0):
    """HTTPS probe that never follows redirects and never raises."""
    t0 = time.time()
    try:
        opener = urlrequest.build_opener(_NoRedirect())
        req = urlrequest.Request(url, headers={"User-Agent": "GalardoEdgeProbe/1.0",
                                               "Cache-Control": "no-cache"})
        with opener.open(req, timeout=timeout) as r:
            body = r.read()
            return {"status": r.getcode(), "header": r.headers.get(OVERRIDE_HEADER),
                    "body_len": len(body), "latency_ms": round((time.time() - t0) * 1000, 1),
                    "url": url}
    except HTTPError as e:
        body = e.read()
        return {"status": e.code, "header": e.headers.get(OVERRIDE_HEADER),
                "body_len": len(body), "latency_ms": round((time.time() - t0) * 1000, 1),
                "url": url}
    except Exception as e:
        return {"status": None, "error": str(e)[:200], "url": url}


class CloudflareClient:
    """Thin, auditable Cloudflare API v4 client. Every call is recorded."""

    def __init__(self, token=None, account_id=None, zone_id=None, timeout=30.0):
        self.token = token or os.environ.get("GALARDO_CF_TOKEN")
        self.account_id = account_id or os.environ.get("GALARDO_CF_ACCOUNT_ID")
        self.zone_id = zone_id or os.environ.get("GALARDO_CF_ZONE_ID")
        self.timeout = float(timeout)
        self.calls = []
        self.last_status = None
        self._zone_name = None

    def available(self):
        return not self.missing()

    def missing(self):
        m = []
        if not self.token:
            m.append("GALARDO_CF_TOKEN")
        if not self.account_id:
            m.append("GALARDO_CF_ACCOUNT_ID")
        if not self.zone_id:
            m.append("GALARDO_CF_ZONE_ID")
        return m

    # ---------------- raw call ----------------
    # ---------------- discovery ----------------
    def discover(self, zone_name=None):
        """Cari zone_id + account_id HANYA dari token (butuh izin Zone:Read)."""
        zone_name = zone_name or os.environ.get("GALARDO_CF_ZONE_NAME")
        out = {"zone_id": self.zone_id, "account_id": self.account_id,
               "zone_name": None, "errors": [], "zones": []}
        if not self.zone_id:
            r = self._req("GET", "/zones?per_page=50")
            if not r.get("_ok"):
                out["errors"].append("GET /zones gagal: %s"
                                     % (r.get("errors") or r.get("_http_status")))
            else:
                zones = r.get("result") or []
                out["zones"] = [z.get("name") for z in zones]
                pick = None
                if zone_name:
                    for z in zones:
                        if z.get("name") == zone_name:
                            pick = z
                            break
                    if pick is None:
                        out["errors"].append("zone '%s' tidak terlihat oleh token" % zone_name)
                elif len(zones) == 1:
                    pick = zones[0]
                elif zones:
                    out["errors"].append("token melihat %d zone; set GALARDO_CF_ZONE_NAME"
                                         % len(zones))
                if pick:
                    self.zone_id = out["zone_id"] = pick.get("id")
                    out["zone_name"] = pick.get("name")
                    if not self.account_id:
                        self.account_id = out["account_id"] = (pick.get("account") or {}).get("id")
        if not self.account_id:
            r = self._req("GET", "/accounts?per_page=50")
            if r.get("_ok") and (r.get("result") or []):
                self.account_id = out["account_id"] = (r["result"][0] or {}).get("id")
        out["ok"] = bool(self.zone_id and self.account_id)
        return out

    def zone_info(self):
        """Status zone: active/pending + nameserver yang seharusnya dipakai."""
        if not self.zone_id:
            return {"ok": False, "detail": "zone_id belum ada"}
        r = self._req("GET", "/zones/%s" % self.zone_id)
        if not r.get("_ok"):
            return {"ok": False, "status_http": r.get("_http_status"), "errors": r.get("errors")}
        z = r.get("result") or {}
        return {"ok": True, "status": z.get("status"), "name": z.get("name"),
                "paused": z.get("paused"), "plan": (z.get("plan") or {}).get("name"),
                "name_servers": z.get("name_servers"),
                "original_ns": z.get("original_name_servers")}

    def _req(self, method, path, body=None, raw=None, ctype="application/json"):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urlrequest.Request(CF_API + path, data=data, method=method)
        req.add_header("Authorization", "Bearer " + str(self.token))
        req.add_header("Content-Type", ctype)
        status, txt = None, ""
        try:
            with urlrequest.build_opener().open(req, timeout=self.timeout) as r:
                status = r.getcode()
                txt = r.read().decode("utf-8", "replace")
        except HTTPError as e:
            status = e.code
            try:
                txt = e.read().decode("utf-8", "replace")
            except Exception:
                txt = ""
        except Exception as e:
            txt = json.dumps({"success": False, "errors": [{"message": str(e)}]})
        try:
            payload = json.loads(txt) if txt else {}
        except Exception:
            payload = {"success": False, "errors": [{"message": txt[:200]}]}
        ok = bool(payload.get("success")) and status is not None and 200 <= status < 300
        self.last_status = status
        self.calls.append({"method": method, "path": path, "status": status, "ok": ok,
                           "errors": [e.get("message") for e in (payload.get("errors") or [])][:2]})
        payload["_http_status"] = status
        payload["_ok"] = ok
        return payload

    # ---------------- helpers ----------------
    def verify_token(self):
        return self._req("GET", "/user/tokens/verify")

    def zone_name(self):
        if self._zone_name:
            return self._zone_name
        r = self._req("GET", "/zones/%s" % self.zone_id)
        if r.get("_ok"):
            self._zone_name = (r.get("result") or {}).get("name")
        return self._zone_name

    def ensure_proxied_host(self, host, ip="192.0.2.1"):
        """A Worker route only fires for PROXIED hostnames. Create/fix the record."""
        r = self._req("GET", "/zones/%s/dns_records?name=%s" % (self.zone_id, quote(host)))
        if not r.get("_ok"):
            return {"ok": False, "detail": "list dns_records gagal", "errors": r.get("errors"),
                    "status": r.get("_http_status")}
        recs = r.get("result") or []
        if recs:
            rec = recs[0]
            if rec.get("proxied"):
                return {"ok": True, "detail": "record sudah proxied", "created": False,
                        "record_id": rec.get("id"), "ip": rec.get("content")}
            p = self._req("PATCH", "/zones/%s/dns_records/%s" % (self.zone_id, rec["id"]),
                          {"proxied": True})
            return {"ok": bool(p.get("_ok")), "detail": "record di-set proxied", "created": False,
                    "record_id": rec.get("id"), "errors": p.get("errors"),
                    "status": p.get("_http_status")}
        c = self._req("POST", "/zones/%s/dns_records" % self.zone_id,
                      {"type": "A", "name": host, "content": ip, "ttl": 1, "proxied": True,
                       "comment": "galardo override"})
        if not c.get("_ok"):
            return {"ok": False, "detail": "create dns_record gagal", "errors": c.get("errors"),
                    "status": c.get("_http_status")}
        return {"ok": True, "detail": "proxied A record dibuat -> %s" % ip, "created": True,
                "record_id": (c.get("result") or {}).get("id")}

    def upload_worker(self, name, js):
        r1 = self._req("PUT", "/accounts/%s/workers/scripts/%s" % (self.account_id, name),
                       raw=js.encode(), ctype="application/javascript")
        if r1.get("_ok"):
            return {"ok": True, "mode": "service-worker", "status": r1["_http_status"]}
        first = r1.get("errors")
        body, ctype = _multipart({"main_module": "worker.js"}, {"worker.js": js})
        r2 = self._req("PUT", "/accounts/%s/workers/scripts/%s" % (self.account_id, name),
                       raw=body, ctype=ctype)
        if r2.get("_ok"):
            return {"ok": True, "mode": "modules", "status": r2["_http_status"]}
        return {"ok": False, "mode": None, "status": r2.get("_http_status"),
                "errors": r2.get("errors"), "service_worker_errors": first}

    def bind_route(self, host, script):
        pattern = host + "/*"
        r = self._req("POST", "/zones/%s/workers/routes" % self.zone_id,
                      {"pattern": pattern, "script": script})
        if r.get("_ok"):
            return {"ok": True, "route_id": (r.get("result") or {}).get("id"),
                    "pattern": pattern, "status": r["_http_status"]}
        return {"ok": False, "errors": r.get("errors"), "status": r.get("_http_status"),
                "pattern": pattern}

    def delete_route(self, route_id):
        return self._req("DELETE", "/zones/%s/workers/routes/%s" % (self.zone_id, route_id))

    def delete_worker(self, name):
        return self._req("DELETE", "/accounts/%s/workers/scripts/%s" % (self.account_id, name))

    def delete_dns_record(self, record_id):
        return self._req("DELETE", "/zones/%s/dns_records/%s" % (self.zone_id, record_id))

    def purge_host(self, host):
        return self._req("POST", "/zones/%s/purge_cache" % self.zone_id,
                         {"files": ["https://%s/" % host, "https://%s" % host]})


class CloudflareEdgeOverride:
    """Tier T3. apply() = dns proxied -> upload worker -> bind route -> verify via edge."""

    TIER = "T3-cf-worker"

    def __init__(self, token=None, account_id=None, zone_id=None, script=None,
                 client=None, host=None, verify=True, verify_retries=8, **kw):
        self.client = client or CloudflareClient(token, account_id, zone_id)
        self.script = script or os.environ.get("GALARDO_CF_SCRIPT", "galardo-override")
        self.host = host or os.environ.get("GALARDO_CF_TEST_HOST")
        self.verify = bool(verify)
        self.verify_retries = int(verify_retries)
        self.state = {}

    def available(self):
        return self.client.available()

    def _worker_name(self, spec):
        raw = "".join(c if c.isalnum() else "-" for c in spec.spec_id.lower())
        return ("%s-%s" % (self.script, raw))[:58]

    def _worker_js(self, spec):
        body = "" if spec.mode == "blank" else ("galardo forced %s" % spec.mode)
        return (WORKER_SOURCE
                .replace("__PATHS__", json.dumps(list(spec.paths)))
                .replace("__STATUS__", str(spec.forced_status()))
                .replace("__MODE__", json.dumps(spec.mode))
                .replace("__BODY__", json.dumps(body)))

    def apply(self, spec):
        if not self.available():
            return TierResult(self.TIER, False,
                              "env belum lengkap: %s" % ", ".join(self.client.missing()))
        zone = self.client.zone_name()
        if not zone:
            return TierResult(self.TIER, False,
                              "tidak bisa baca zone (cek GALARDO_CF_ZONE_ID + izin token)")
        host = self.host or ("galardo-edge." + zone)
        if not host.endswith(zone):
            return TierResult(self.TIER, False,
                              "host %s tidak berada di zone %s" % (host, zone))
        worker = self._worker_name(spec)
        steps = {}

        steps["dns"] = self.client.ensure_proxied_host(host)
        if not steps["dns"].get("ok"):
            return TierResult(self.TIER, False, "DNS: %s" % steps["dns"].get("detail"),
                              {"host": host, "steps": steps})

        steps["upload"] = self.client.upload_worker(worker, self._worker_js(spec))
        if not steps["upload"].get("ok"):
            return TierResult(self.TIER, False,
                              "upload worker gagal (HTTP %s)" % steps["upload"].get("status"),
                              {"host": host, "steps": steps},
                              status_code=steps["upload"].get("status"))

        steps["route"] = self.client.bind_route(host, worker)
        if not steps["route"].get("ok"):
            self.client.delete_worker(worker)
            return TierResult(self.TIER, False,
                              "bind route gagal (HTTP %s)" % steps["route"].get("status"),
                              {"host": host, "steps": steps},
                              status_code=steps["route"].get("status"))

        try:
            steps["purge"] = {"ok": bool(self.client.purge_host(host).get("_ok"))}
        except Exception:
            steps["purge"] = {"ok": False}

        p0 = spec.paths[0].rstrip("*").rstrip("/") or "/"
        probe = None
        if self.verify:
            probe = self.verify_forced(host, p0, spec.forced_status(), spec.mode)

        self.state[spec.spec_id] = {"host": host, "worker": worker,
                                    "route_id": steps["route"].get("route_id"),
                                    "dns_record_id": steps["dns"].get("record_id"),
                                    "dns_created": bool(steps["dns"].get("created")),
                                    "mode": spec.mode, "paths": list(spec.paths),
                                    "at": time.time()}
        ok = True
        if self.verify and probe:
            ok = (probe.get("status") == spec.forced_status()
                  and probe.get("header") == spec.mode)
        detail = ("edge LIVE: https://%s%s -> %s + %s:%s (%s attempt)"
                  % (host, p0, probe.get("status") if probe else "?",
                     OVERRIDE_HEADER, probe.get("header") if probe else "?",
                     probe.get("attempts") if probe else "n/a"))
        artifact = {"host": host, "worker": worker, "route_id": steps["route"].get("route_id"),
                    "upload_mode": steps["upload"].get("mode"),
                    "upload_status": steps["upload"].get("status"),
                    "route_status": steps["route"].get("status"),
                    "dns_status": steps["dns"].get("status"),
                    "probe": probe, "steps": steps}
        return TierResult(self.TIER, bool(ok), detail, artifact,
                          status_code=steps["route"].get("status"))

    def verify_forced(self, host, path, expect_status, mode, retries=None, delay=3.0):
        """Edge butuh beberapa detik untuk aktif -> retry, dan catat jumlah percobaan."""
        retries = retries or self.verify_retries
        last = None
        for i in range(retries):
            url = "https://%s%s?_gcb=%d" % (host, path, int(time.time() * 1000))
            last = _edge_probe(url)
            if last.get("status") == expect_status and last.get("header") == mode:
                last["attempts"] = i + 1
                return last
            time.sleep(delay)
        if last is not None:
            last["attempts"] = retries
        return last

    def revert(self, spec_id):
        st = self.state.pop(spec_id, None)
        if not st:
            return TierResult(self.TIER, False, "tidak ada state T3 untuk %s" % spec_id)
        out = {}
        if st.get("route_id"):
            out["route_deleted"] = bool(self.client.delete_route(st["route_id"]).get("_ok"))
        if st.get("worker"):
            out["worker_deleted"] = bool(self.client.delete_worker(st["worker"]).get("_ok"))
        if st.get("dns_record_id") and st.get("dns_created"):
            out["dns_deleted"] = bool(self.client.delete_dns_record(st["dns_record_id"]).get("_ok"))
        return TierResult(self.TIER, True, "T3 reverted: %s" % json.dumps(out), out)

    def evidence(self):
        return {"tier": self.TIER, "available": self.available(),
                "missing_env": self.client.missing(), "host_override": self.host,
                "script": self.script, "active": list(self.state.keys()),
                "api_calls": self.client.calls[-40:]}


# ---------------------------------------------------------------------------
# Cert authority (best-effort, needed only for HTTPS on the real hostname)
# ---------------------------------------------------------------------------
class CertAuthority:
    TIER = "T4-cert"

    def __init__(self, base_dir=None, **kw):
        self.base_dir = base_dir or os.path.join(os.path.expanduser("~"), ".galardo", "certs")

    def available(self):
        return bool(shutil.which("openssl"))

    def generate(self, host):
        if not self.available():
            return TierResult(self.TIER, False, "openssl not found")
        d = os.path.join(self.base_dir, host)
        os.makedirs(d, exist_ok=True)
        key = os.path.join(d, "key.pem")
        crt = os.path.join(d, "cert.pem")
        if not (os.path.exists(key) and os.path.exists(crt)):
            base = ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", key, "-out", crt, "-days", "365", "-subj", "/CN=%s" % host]
            p = subprocess.run(base + ["-addext", "subjectAltName=DNS:%s" % host],
                               capture_output=True, text=True)
            if p.returncode != 0:
                p = subprocess.run(base, capture_output=True, text=True)
            if p.returncode != 0:
                return TierResult(self.TIER, False, (p.stderr or "")[:200])
        return TierResult(self.TIER, True, "cert ready", {"cert": crt, "key": key, "host": host})


# ---------------------------------------------------------------------------
# Orchestrator of tiers
# ---------------------------------------------------------------------------
class RouteOverrider:
    """apply() tries tiers in order; the first success wins and is recorded."""

    def __init__(self, spec=None, upstream=None, connect_ip=None, shim_port=None,
                 tier_order=None, cf=None, hosts=None, certs=None, **kw):
        self.upstream = upstream
        self.connect_ip = connect_ip
        self.shim_port = int(shim_port) if shim_port else None
        self.tier_order = tuple(tier_order or ("T2", "T1", "T3"))
        self.shims: Dict[str, LocalShim] = {}
        self.active: Dict[str, dict] = {}
        self.spec = spec
        self.shim = None
        self.attempts: List[dict] = []
        self.lock = threading.Lock()
        self.hosts = hosts or HostsOverride()
        self.cf = cf or CloudflareEdgeOverride()
        self.certs = certs or CertAuthority()

    def _try(self, tier, spec):
        if tier == "T2":
            shim = LocalShim(spec, port=self.shim_port, upstream=self.upstream,
                             connect_ip=self.connect_ip).start()
            p0 = spec.paths[0].rstrip("*").rstrip("/") or "/"
            pr = shim.probe(p0)
            ok = pr.get("status") == spec.forced_status() and bool(pr.get("override_header"))
            if ok:
                with self.lock:
                    self.shims[spec.spec_id] = shim
            else:
                shim.stop()
            return TierResult(tier, ok, "shim probe: %s" % json.dumps(pr)[:200],
                              {"shim_url": shim.url()}, status_code=pr.get("status"))
        if tier == "T1":
            return self.hosts.apply(spec.host())
        if tier == "T3":
            return self.cf.apply(spec)
        return TierResult(tier, False, "unknown tier")

    def prepare(self, spec):
        self.spec = _coerce_spec(spec)
        return self.spec

    def apply(self, spec=None, tiers=None):
        spec = _coerce_spec(spec) if spec is not None else self.spec
        if spec is None:
            raise ValueError("no spec supplied and none prepared via prepare()/self.spec")
        self.spec = spec
        order = tiers or spec.tiers or self.tier_order
        results, applied, failed = [], [], []
        for t in order:
            r = self._try(t, spec)
            results.append(asdict(r))
            (applied if r.ok else failed).append(t)
            with self.lock:
                self.attempts.append({"spec_id": spec.spec_id, "tier": t, "ok": r.ok,
                                      "at": time.time(), "detail": r.detail})
            if r.ok:
                with self.lock:
                    self.active[spec.spec_id] = {"tier": t, "at": time.time(),
                                                 "spec": spec.to_dict(), "artifact": r.artifact}
                    self.shim = self.shims.get(spec.spec_id)
                return {"ok": True, "tier": t,
                        "applied_tiers": applied, "failed_tiers": failed,
                        "global_scope": any(x in ("T1", "T3") for x in applied),
                        "spec": spec.to_dict(),
                        "shim_url": self.shim_url(spec.spec_id),
                        "upstream": self.upstream, "connect_ip": self.connect_ip,
                        "shim_port": self.shim_port, "results": results}
        return {"ok": False, "tier": None, "applied_tiers": applied,
                "failed_tiers": failed, "global_scope": False,
                "spec": spec.to_dict(), "results": results}

    def shim_url(self, spec_id):
        s = self.shims.get(spec_id)
        return s.url() if s else None

    def probe(self, spec_id, path=None):
        s = self.shims.get(spec_id)
        act = self.active.get(spec_id)
        if not s or not act:
            return {"ok": False, "error": "no active shim override for %s" % spec_id}
        p = path or (act["spec"]["paths"][0] if act["spec"]["paths"][0] != "*" else "/")
        pr = s.probe(p)
        pr["forced"] = bool(pr.get("override_header"))
        pr["matches_spec"] = pr.get("status") == act["spec"]["forced_status"]
        pr["tier"] = act["tier"]
        return pr

    def revert(self, spec_id=None):
        spec_id = spec_id or (self.spec.spec_id if self.spec else None)
        with self.lock:
            s = self.shims.pop(spec_id, None)
            act = self.active.pop(spec_id, None)
            if self.shim is s:
                self.shim = None
        if s:
            s.stop()
        tier = act["tier"] if act else None
        if act and tier == "T1":
            self.hosts.revert()
        if act and tier == "T3":
            try:
                self.cf.revert(spec_id)
            except Exception:
                pass
        return {"ok": bool(act), "spec_id": spec_id,
                "reverted": [tier] if tier else [],
                "reverted_tiers": [tier] if tier else [],
                "tier": tier}

    def list_active(self):
        with self.lock:
            return {k: dict(v, shim_url=self.shim_url(k)) for k, v in self.active.items()}

    def evidence(self):
        with self.lock:
            return {"tier_order": list(self.tier_order),
                    "active": list(self.active.keys()),
                    "attempts": self.attempts[-20:],
                    "spec": self.spec.to_dict() if self.spec else None,
                    "upstream": self.upstream, "connect_ip": self.connect_ip,
                    "shim_port": self.shim_port,
                    "shim_url": self.shim.url_for("/") if self.shim else None}

    def stats(self):
        with self.lock:
            return {"active": len(self.active), "shims": len(self.shims),
                    "attempts": self.attempts[-20:], "tier_order": list(self.tier_order)}


# ---------------------------------------------------------------------------
# compat-w7: module-level functional API expected by api.py
# ---------------------------------------------------------------------------
REGISTRY = RouteOverrider()

# module-level mirror so `import routeoverride as ro; ro.spec = ...; ro.apply(tiers=..)`
# and `ro.shim.url_for("/")` both work whether `ro` is the module or the registry.
spec = None
shim = None


def _coerce_spec(obj):
    if isinstance(obj, OverrideSpec):
        return obj
    if isinstance(obj, dict):
        d = dict(obj)
        d.setdefault("origin", d.get("domain") or d.get("target") or d.get("url") or "")
        d.setdefault("paths", ["/*"])
        d.setdefault("mode", "404")
        allowed = ("origin", "paths", "mode", "spec_id", "shim_port", "tiers", "upstream",
                   "host_header", "port", "label", "hosts", "note")
        d = {k: v for k, v in d.items() if k in allowed}
        if isinstance(d.get("paths"), str):
            d["paths"] = [d["paths"]]
        return OverrideSpec(**d)
    raise TypeError("cannot coerce %r to OverrideSpec" % type(obj))


def prepare(sp):
    global spec
    spec = _coerce_spec(sp)
    REGISTRY.prepare(spec)
    return spec


def apply(sp=None, tiers=None, **kw):
    global spec, shim
    target = _coerce_spec(sp) if sp is not None else spec
    if target is None:
        raise ValueError("routeoverride.apply: no spec (set routeoverride.spec or pass one)")
    spec = target
    out = REGISTRY.apply(target, tiers=tiers)
    shim = REGISTRY.shim
    return out


def applied():
    return REGISTRY.list_active()


def applied_list():
    return [dict(v.get("spec") or {}, spec_id=k, tier=v.get("tier"))
            for k, v in REGISTRY.list_active().items()]


def reverted(spec_id):
    global shim
    out = REGISTRY.revert(spec_id)
    shim = REGISTRY.shim
    return out


def test(spec_id, path=None):
    return REGISTRY.probe(spec_id, path)


def get(spec_id):
    return REGISTRY.active.get(spec_id)


def probe(spec_id, path=None):
    return REGISTRY.probe(spec_id, path)


def revert(spec_id):
    global shim
    out = REGISTRY.revert(spec_id)
    shim = REGISTRY.shim
    return out


def list_active():
    return REGISTRY.list_active()


def stats():
    return REGISTRY.stats()
