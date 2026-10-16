"""GALARDO - Out-of-band probe + DOWN state machine + watcher (GOAL 2).

Contract: the probe is INDEPENDENT of the load generator (TD 10, FR-08).
It runs on its own socket and its own thread, samples the target, and drives
an explicit, auditable state machine:

    UP -> SUSPECT -> DOWN -> RECOVERING -> RECOVERED

Hard rules enforced here:
  * failure_threshold consecutive failures before SUSPECT (no flapping)
  * min_down_seconds of sustained failure before DOWN (no false DOWN)
  * time_to_recover measured from DOWN entry to RECOVERED (never guessed)
  * every transition is timestamped and carries its reason string
  * a probe thread NEVER dies: the loop body is wrapped and records last_error
"""
import random
import socket
import ssl
import threading
import time
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, urlencode

FAILURE_OK = "OK"
FAILURE_TIMEOUT = "TIMEOUT"
FAILURE_CONN = "CONN"
FAILURE_HTTP = "HTTP_STATUS"
FAILURE_TLS = "TLS"
FAILURE_DNS = "DNS"
FAILURE_CRASH = "CRASH"

STATE_UP = "UP"
STATE_SUSPECT = "SUSPECT"
STATE_DOWN = "DOWN"
STATE_RECOVERING = "RECOVERING"
STATE_RECOVERED = "RECOVERED"

DEFAULT_MAX_SAMPLES = 4096


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
class _NoRedirect(urlrequest.HTTPRedirectHandler):
    """Do not follow 3xx: we need the raw status for override detection."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _opener(tls_verify=True):
    # pakai netssl: bundle CA sistem bisa tidak valid
    ctx = _ns.context(verify=tls_verify)
    return urlrequest.build_opener(_NoRedirect(), urlrequest.HTTPSHandler(context=ctx))


def _as_status_set(v):
    if v is None:
        return {200}
    if isinstance(v, int):
        return {v}
    if isinstance(v, str):
        s = v.replace(",", " ").split()
        return {int(p) for p in s} if s else {200}
    return {int(p) for p in v}


def _res(ok, reason, status, latency_ms, error, url):
    return {"ok": bool(ok), "reason": reason, "status": status,
            "latency_ms": round(latency_ms, 3) if latency_ms is not None else None,
            "error": error, "url": url, "at": time.time()}


def _pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    k = int(round((p / 100.0) * (len(s) - 1)))
    return round(s[max(0, min(k, len(s) - 1))], 3)


_BC_SEQ = [0]
_BC_LOCK = threading.Lock()

try:
    from . import cachebuster as _cb
except ImportError:
    import cachebuster as _cb

try:
    from . import layer_attrib as _la
except ImportError:
    import layer_attrib as _la

try:
    from . import netssl as _ns
except ImportError:
    import netssl as _ns


def cache_buster_token():
    with _BC_LOCK:
        _BC_SEQ[0] += 1
        return "%d.%d.%d" % (int(time.time() * 1000), _BC_SEQ[0], random.randint(0, 9999))


def cache_buster_path(url, token=None):
    """Param nonce unik supaya cache CDN tak menyajikan body basi.

    Penanda KANONIK = cachebuster.BUSTER_KEY ("__gb"), disatukan dengan engine
    dan cachebuster.py supaya evidence tidak bercampur dua penanda berbeda.
    """
    tok = token or cache_buster_token()
    decorated, _ = _cb.decorate(url, _cb.BUSTER_KEY, tok)
    return decorated


def probe_http_raw(url, timeout=1.5, expected_status=(200,), tls_verify=True,
                   method="GET", headers=None):
    """Single out-of-band HTTP sample. Returns a result dict, never raises."""
    exp = _as_status_set(expected_status)
    t0 = time.time()
    req = urlrequest.Request(url, method=method, headers=dict(headers or {}))
    req.add_header("User-Agent", "GalardoProbe/1.0")
    req.add_header("Cache-Control", "no-cache")
    try:
        with _opener(tls_verify).open(req, timeout=timeout) as resp:
            status = resp.getcode()
            try:
                resp.read(2048)
            except Exception:
                pass
            lat = (time.time() - t0) * 1000.0
            if status in exp:
                return _res(True, FAILURE_OK, status, lat, None, url)
            return _res(False, FAILURE_HTTP, status, lat,
                        "status %s not in %s" % (status, sorted(exp)), url)
    except HTTPError as e:
        lat = (time.time() - t0) * 1000.0
        status = getattr(e, "code", None)
        if status in exp:
            return _res(True, FAILURE_OK, status, lat, None, url)
        return _res(False, FAILURE_HTTP, status, lat,
                    "status %s not in %s" % (status, sorted(exp)), url)
    except socket.timeout:
        return _res(False, FAILURE_TIMEOUT, None, (time.time() - t0) * 1000.0,
                    "timeout after %.2fs" % timeout, url)
    except ssl.SSLError as e:
        return _res(False, FAILURE_TLS, None, (time.time() - t0) * 1000.0, str(e)[:200], url)
    except URLError as e:
        r = e.reason
        lat = (time.time() - t0) * 1000.0
        if isinstance(r, socket.timeout):
            return _res(False, FAILURE_TIMEOUT, None, lat, "timeout after %.2fs" % timeout, url)
        if isinstance(r, ssl.SSLError):
            return _res(False, FAILURE_TLS, None, lat, str(r)[:200], url)
        if isinstance(r, socket.gaierror):
            return _res(False, FAILURE_DNS, None, lat, str(r)[:200], url)
        return _res(False, FAILURE_CONN, None, lat, str(r)[:200], url)
    except Exception as e:
        return _res(False, FAILURE_CRASH, None, (time.time() - t0) * 1000.0, str(e)[:200], url)


def attribute(result, cdn=None, control_ok=True):
    """Lampirkan atribusi lapisan (dns/edge/origin/app/ours) pada hasil probe.

    Vonis "DOWN" tanpa lapisan itu menyesatkan: DNS mati, edge mati, origin mati,
    dan aplikasi error butuh tindakan berbeda.
    """
    r = dict(result or {})
    if r.get("ok"):
        r["layer"] = "healthy"
        return r
    reason = r.get("reason")
    obs = {}
    if reason == FAILURE_DNS:
        obs["dns"] = {"ok": False, "rcode": "GAIERROR"}
    elif reason == FAILURE_TIMEOUT:
        obs["http"] = {"ok": False, "error": r.get("error") or "timed out"}
    elif reason == FAILURE_CONN:
        obs["tcp"] = {"ok": False, "error": r.get("error") or "connection failed"}
    elif reason == FAILURE_TLS:
        obs["tls"] = {"ok": False, "error": r.get("error") or "tls failed"}
    elif reason == FAILURE_HTTP:
        obs["http"] = {"ok": False, "status": r.get("status")}
    else:
        obs["http"] = {"ok": False, "error": r.get("error") or str(reason)}
    if cdn:
        obs["cdn"] = cdn
    try:
        res = _la.classify(obs, control_ok=control_ok)
    except Exception as e:
        res = {"layer": "unknown", "reason": "atribusi gagal: %s" % e,
               "confidence": "low", "tier_hint": "", "evidence": {}}
    r["layer"] = res.get("layer")
    r["layer_reason"] = res.get("reason")
    r["layer_confidence"] = res.get("confidence")
    r["layer_hint"] = res.get("tier_hint")
    return r


def probe_http(url, timeout=1.5, expected_status=(200,), tls_verify=True,
               method="GET", headers=None):
    """probe_http_raw + atribusi lapisan pada hasilnya."""
    return attribute(probe_http_raw(url, timeout=timeout,
                                    expected_status=expected_status,
                                    tls_verify=tls_verify, method=method,
                                    headers=headers))


def probe_tcp(host, port, timeout=1.5):
    """L4 reachability sample (does not prove the app answered)."""
    t0 = time.time()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return _res(True, FAILURE_OK, None, (time.time() - t0) * 1000.0, None,
                    "tcp://%s:%s" % (host, port))
    except socket.timeout:
        return _res(False, FAILURE_TIMEOUT, None, (time.time() - t0) * 1000.0,
                    "tcp timeout", "tcp://%s:%s" % (host, port))
    except Exception as e:
        return _res(False, FAILURE_CONN, None, (time.time() - t0) * 1000.0,
                    str(e)[:200], "tcp://%s:%s" % (host, port))


# ---------------------------------------------------------------------------
# state machine
# ---------------------------------------------------------------------------
class DownStateMachine:
    """Deterministic, auditable UP/SUSPECT/DOWN/RECOVERING/RECOVERED machine."""

    def __init__(self, failure_threshold=4, min_down_seconds=6.0,
                 recover_threshold=3, recover_seconds=3.0,
                 on_transition=None, clock=time.time):
        self.failure_threshold = max(1, int(failure_threshold))
        self.min_down_seconds = float(min_down_seconds)
        self.recover_threshold = max(1, int(recover_threshold))
        self.recover_seconds = float(recover_seconds)
        self.on_transition = on_transition
        self.clock = clock
        self.state = STATE_UP
        self.fail_streak = 0
        self.ok_streak = 0
        self.suspect_since = None
        self.down_at = None
        self.recovering_since = None
        self.time_to_recover = None
        self.down_count = 0
        self.transitions = []
        self.last_reason = ""
        self.last_failure_reason = None
        self.last_layer = None

    def _to(self, new, reason):
        old = self.state
        if old == new:
            return None
        now = self.clock()
        self.state = new
        if new == STATE_SUSPECT:
            self.suspect_since = now
        elif new == STATE_DOWN:
            self.down_at = now
            self.down_count += 1
        elif new == STATE_RECOVERING:
            self.recovering_since = now
        elif new == STATE_RECOVERED:
            if self.down_at is not None:
                self.time_to_recover = round(now - self.down_at, 3)
            self.recovering_since = None
        ev = {"from": old, "to": new, "reason": reason, "at": now,
              "at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))}
        self.transitions.append(ev)
        if self.on_transition:
            try:
                self.on_transition(ev)
            except Exception:
                pass
        return ev

    def on_sample(self, ok, reason="", layer=None):
        now = self.clock()
        self.last_reason = reason or ""
        if layer:
            self.last_layer = layer
        if not ok:
            self.ok_streak = 0
            self.fail_streak += 1
            self.last_failure_reason = reason
        else:
            self.fail_streak = 0
            self.ok_streak += 1

        if self.state == STATE_UP:
            if not ok and self.fail_streak >= self.failure_threshold:
                self._to(STATE_SUSPECT,
                         "fail_streak=%d >= %d (%s)" % (self.fail_streak, self.failure_threshold, reason))
        elif self.state == STATE_SUSPECT:
            if ok:
                self._to(STATE_UP, "answered again before DOWN (%s)" % reason)
            elif self.suspect_since is not None and (now - self.suspect_since) >= self.min_down_seconds:
                self._to(STATE_DOWN, "sustained failure %.2fs >= %.2fs"
                         % (now - self.suspect_since, self.min_down_seconds))
        elif self.state == STATE_DOWN:
            if ok and self.ok_streak >= self.recover_threshold:
                self._to(STATE_RECOVERING, "ok_streak=%d >= %d" % (self.ok_streak, self.recover_threshold))
        elif self.state == STATE_RECOVERING:
            if not ok:
                self._to(STATE_DOWN, "relapse during recovery (%s)" % reason)
            elif self.recovering_since is not None and (now - self.recovering_since) >= self.recover_seconds:
                self._to(STATE_RECOVERED, "stable %.2fs" % (now - self.recovering_since))
        elif self.state == STATE_RECOVERED:
            if not ok and self.fail_streak >= self.failure_threshold:
                self._to(STATE_SUSPECT, "re-entry after recovery")
        return self.state

    def evidence(self):
        return {
            "state": self.state,
            "down_verified": self.down_count > 0,
            "down_count": self.down_count,
            "time_to_recover": self.time_to_recover,
            "down_at": self.down_at,
            "transitions": list(self.transitions),
            "failure_threshold": self.failure_threshold,
            "min_down_seconds": self.min_down_seconds,
            "recover_threshold": self.recover_threshold,
            "recover_seconds": self.recover_seconds,
            "last_reason": self.last_reason,
            "last_failure_reason": self.last_failure_reason,
            "last_layer": self.last_layer,
        }

    def verdict(self):
        return self.evidence()


# ---------------------------------------------------------------------------
# probe thread
# ---------------------------------------------------------------------------
class ExternalProbe(threading.Thread):
    """Sampling thread. Never dies; records last_error instead."""

    def __init__(self, url, interval=0.5, timeout=1.5, expected_status=(200,),
                 tls_verify=True, max_samples=DEFAULT_MAX_SAMPLES, on_sample=None,
                 cache_buster=True, name=None):
        threading.Thread.__init__(self, daemon=True, name=name or "galardo-probe")
        self.url = url
        self.interval = float(interval)
        self.timeout = float(timeout)
        self.expected_status = _as_status_set(expected_status)
        self.tls_verify = bool(tls_verify)
        self.max_samples = int(max_samples)          # bug #1: was never assigned
        self.on_sample = on_sample
        self.cache_buster = bool(cache_buster)
        self.stop = threading.Event()
        self.samples = []
        self.failures = 0
        self.last_error = None                       # bug #1: was never assigned
        self.last_result = None
        self.lock = threading.Lock()

    def run(self):
        while not self.stop.is_set():
            t0 = time.time()
            try:
                url = cache_buster_path(self.url) if self.cache_buster else self.url
                r = probe_http(url, timeout=self.timeout,
                               expected_status=self.expected_status,
                               tls_verify=self.tls_verify)
            except Exception as e:                   # never die
                r = _res(False, FAILURE_CRASH, None, (time.time() - t0) * 1000.0,
                         "probe crash: %s" % e, self.url)
            try:
                self._record(r)
                if self.on_sample:
                    self.on_sample(r)
            except Exception as e:
                with self.lock:
                    self.last_error = "on_sample failed: %s" % e
            sleep = self.interval - (time.time() - t0)
            if sleep > 0:
                self.stop.wait(sleep)

    def _record(self, r):
        with self.lock:
            self.last_result = r
            if not r["ok"]:
                self.failures += 1
                self.last_error = r.get("error")
            self.samples.append(r)
            if len(self.samples) > self.max_samples:
                del self.samples[:len(self.samples) - self.max_samples]

    def snapshot(self):
        with self.lock:
            total = len(self.samples)
            errs = sum(1 for s in self.samples if not s["ok"])
            lats = [s["latency_ms"] for s in self.samples if s.get("latency_ms")]
            last = self.last_result or {}
            return {
                "url": self.url,
                "running": self.is_alive(),
                "interval_sec": self.interval,
                "timeout_sec": self.timeout,
                "samples_total": total,
                "failures": errs,
                "error_ratio_pct": round(100.0 * errs / total, 2) if total else 0.0,
                "last_reason": last.get("reason"),
                "last_layer": last.get("layer"),
                "last_error": self.last_error,
                "last_latency_ms": last.get("latency_ms"),
                "p50_ms": _pct(lats, 50),
                "p95_ms": _pct(lats, 95),
            }

    @property
    def history(self):
        with self.lock:
            return list(self.samples)


# ---------------------------------------------------------------------------
# watcher = probe + state machine
# ---------------------------------------------------------------------------
class DownWatcher:
    """Ties a probe to a state machine. This is the GOAL 2 evidence source."""

    def __init__(self, url, interval=0.5, timeout=1.5, failure_threshold=4,
                 min_down_seconds=6.0, recover_threshold=3, recover_seconds=3.0,
                 on_transition=None, expected_status=(200,), tls_verify=True,
                 max_samples=DEFAULT_MAX_SAMPLES, cache_buster=True):
        self.sm = DownStateMachine(
            failure_threshold=failure_threshold,
            min_down_seconds=min_down_seconds,
            recover_threshold=recover_threshold,
            recover_seconds=recover_seconds,
            on_transition=on_transition)
        self.probe = ExternalProbe(
            url, interval=interval, timeout=timeout,
            expected_status=expected_status, tls_verify=tls_verify,
            max_samples=max_samples, cache_buster=cache_buster,
            on_sample=lambda r: self.sm.on_sample(
                r["ok"], r.get("error") or r.get("reason") or "", r.get("layer")))

    def start(self):
        self.probe.start()
        return self

    def stop(self):
        self.probe.stop.set()

    def is_alive(self):
        return self.probe.is_alive()

    def join(self, t=None):
        self.probe.join(t)

    def snapshot(self):
        d = self.probe.snapshot()
        ev = self.sm.evidence()
        d.update(ev)
        d["verdict"] = ev
        d["down_verdict"] = ev
        return d

    def verdict(self):
        return self.snapshot()

    def evidence(self):
        return self.snapshot()

    def wait_for(self, state, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.sm.state == state:
                return True
            time.sleep(0.25)
        return False
