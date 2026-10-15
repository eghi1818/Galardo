"""Out-of-band DOWN probe (Goal 2). Standard library only.

The load engine and this probe must not share fate. If the generator runs out
of sockets, threads or CPU, an in-band probe would report the target as DOWN
when the target is fine. So this module owns its own thread, its own
Transport, and a tiny request rate.

Two independent signals per cycle:
  * HTTP probe - GET, no redirect follow, bounded read, cache-busted URL
  * TCP probe  - raw connect to host:port, no HTTP layer at all

A DOWN verdict requires SUSTAINED evidence (streak AND duration), and every
DOWN carries a time_to_recover: a spike that never recovers was not a spike.

Python 3.9 compatible.
"""

from __future__ import annotations

import random
import socket
import threading
import time
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
    "ProbeSample", "DownStateMachine", "ExternalProbe", "DownWatcher",
    "cache_buster_path", "probe_http", "probe_tcp",
    "STATE_UP", "STATE_SUSPECT", "STATE_DOWN", "STATE_RECOVERING", "STATE_RECOVERED",
    "FAILURE_TIMEOUT", "FAILURE_CONN", "FAILURE_HTTP", "FAILURE_TLS",
]

STATE_UP = "UP"
STATE_SUSPECT = "SUSPECT"
STATE_DOWN = "DOWN"
STATE_RECOVERING = "RECOVERING"
STATE_RECOVERED = "RECOVERED"

FAILURE_TIMEOUT = "timeout"
FAILURE_CONN = "conn"
FAILURE_HTTP = "http_status"
FAILURE_TLS = "tls"

DEFAULT_NONCE_KEY = "__gb"


def cache_buster_path(path="/", nonce=None, key=DEFAULT_NONCE_KEY):
    """Append a unique query parameter so a CDN cache cannot answer for origin.

    Without this, hitting a Cloudflare-fronted hostname only tests the edge.
    """
    if not path:
        path = "/"
    if nonce is None:
        nonce = "%d%04d" % (int(time.time() * 1000), random.randint(0, 9999))
    separator = "&" if "?" in path else "?"
    return "%s%s%s=%s" % (path, separator, key, nonce)


class ProbeSample(object):
    __slots__ = ("ts", "kind", "ok", "status", "latency_ms", "error",
                 "failure_class", "url")

    def __init__(self, kind, ok, status=None, latency_ms=None, error=None,
                 failure_class=None, url=None, ts=None):
        self.ts = ts or time.time()
        self.kind = kind
        self.ok = bool(ok)
        self.status = status
        self.latency_ms = latency_ms
        self.error = error
        self.failure_class = failure_class
        self.url = url

    def to_dict(self):
        return {"ts": now_iso(), "kind": self.kind, "ok": self.ok,
                "status": self.status, "latency_ms": self.latency_ms,
                "error": self.error, "failure_class": self.failure_class,
                "url": self.url}

    def __repr__(self):
        return "<ProbeSample %s ok=%s status=%s err=%s>" % (
            self.kind, self.ok, self.status, self.error)


def _classify(error):
    if not error:
        return None
    text = str(error).lower()
    if "timeout" in text or "timed out" in text:
        return FAILURE_TIMEOUT
    if "ssl" in text or "certificate" in text:
        return FAILURE_TLS
    return FAILURE_CONN


def probe_http(url, timeout=2.0, connect_ip=None, transport=None, ok_max_status=499,
               method="GET", extra_headers=None):
    """One HTTP probe. Never follows redirects. Returns a ProbeSample."""
    owns_transport = transport is None
    client = transport or transport_mod.Transport(timeout=timeout, max_idle=4)
    headers = {"User-Agent": "galardo-probe/1.0 (out-of-band)",
               "Cache-Control": "no-cache", "Pragma": "no-cache"}
    if extra_headers:
        headers.update(extra_headers)
    try:
        resp = client.request(method, url, headers=headers, timeout=timeout,
                              allow_redirects=False, connect_ip=connect_ip)
        if resp.error:
            return ProbeSample("http", False, error=resp.error,
                               failure_class=_classify(resp.error), url=url)
        ok = resp.status is not None and resp.status <= ok_max_status
        return ProbeSample("http", ok, status=resp.status, latency_ms=resp.elapsed_ms,
                           error=None if ok else "http %s" % resp.status,
                           failure_class=None if ok else FAILURE_HTTP, url=url)
    finally:
        if owns_transport:
            client.close()


def probe_tcp(host, port, timeout=1.5):
    """Raw TCP connect. Proves the socket layer, not the application."""
    started = time.time()
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout)
        return ProbeSample("tcp", True, latency_ms=(time.time() - started) * 1000.0)
    except Exception as exc:
        message = "%s: %s" % (type(exc).__name__, exc)
        return ProbeSample("tcp", False, latency_ms=(time.time() - started) * 1000.0,
                           error=message, failure_class=_classify(message))
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


class DownStateMachine(object):
    """Sustained-evidence DOWN with mandatory RECOVERY accounting.

    DOWN needs BOTH a failure streak and a minimum duration, so a single blip
    never flips the verdict. A raw-timeout streak qualifies faster because a
    TCP timeout is a stronger signal than an HTTP status.
    """

    def __init__(self, failure_threshold=5, min_down_seconds=10.0,
                 recover_threshold=3, recover_seconds=5.0, timeout_streak=3,
                 on_transition=None, clock=time.time):
        self.failure_threshold = failure_threshold
        self.min_down_seconds = min_down_seconds
        self.recover_threshold = recover_threshold
        self.recover_seconds = recover_seconds
        self.timeout_streak = timeout_streak
        self.on_transition = on_transition
        self.clock = clock
        self.state = STATE_UP
        self.consecutive_fail = 0
        self.consecutive_ok = 0
        self.consecutive_timeout = 0
        self.first_fail_ts = None
        self.last_fail_ts = None
        self.down_since = None
        self.recovered_at = None
        self.time_to_recover = None
        self.transitions = []
        self._lock = threading.Lock()

    def _transition(self, new_state, reason):
        if new_state == self.state:
            return
        previous = self.state
        self.state = new_state
        event = {"at": now_iso(), "from": previous, "to": new_state, "reason": reason}
        self.transitions.append(event)
        self.transitions[:] = self.transitions[-100:]
        if self.on_transition:
            try:
                self.on_transition(event)
            except Exception:
                pass

    def feed(self, sample):
        with self._lock:
            now = self.clock()
            if sample.ok:
                self.consecutive_ok += 1
                self.consecutive_fail = 0
                self.consecutive_timeout = 0
                self.first_fail_ts = None
                if self.state in (STATE_DOWN, STATE_RECOVERING, STATE_SUSPECT):
                    sustained_ok = self.consecutive_ok >= self.recover_threshold
                    quiet = (self.last_fail_ts is not None
                             and (now - self.last_fail_ts) >= self.recover_seconds)
                    if sustained_ok and quiet:
                        if self.down_since is not None:
                            self.time_to_recover = round(now - self.down_since, 2)
                        self.recovered_at = now
                        self._transition(STATE_RECOVERED,
                                         "recovered after %d consecutive OK" % self.consecutive_ok)
                return self.state

            self.consecutive_fail += 1
            self.consecutive_ok = 0
            self.last_fail_ts = now
            if self.first_fail_ts is None:
                self.first_fail_ts = now
            if sample.failure_class == FAILURE_TIMEOUT:
                self.consecutive_timeout += 1
            else:
                self.consecutive_timeout = 0

            if self.state in (STATE_UP, STATE_RECOVERED):
                self._transition(STATE_SUSPECT, "first failure: %s" % (sample.error or "?"))

            if self.state == STATE_SUSPECT:
                sustained = (now - self.first_fail_ts) >= self.min_down_seconds
                streak = self.consecutive_fail >= self.failure_threshold
                fast = self.consecutive_timeout >= self.timeout_streak
                if sustained and (streak or fast):
                    self.down_since = self.first_fail_ts
                    self.time_to_recover = None
                    self._transition(STATE_DOWN,
                                     "sustained: streak=%d over %.1fs (fast=%s)" % (
                                         self.consecutive_fail, now - self.first_fail_ts, fast))
            return self.state

    def snapshot(self):
        with self._lock:
            return {"state": self.state,
                    "consecutive_fail": self.consecutive_fail,
                    "consecutive_ok": self.consecutive_ok,
                    "down_since": self.down_since,
                    "down_since_iso": (now_iso() if self.down_since is None
                                       else _iso(self.down_since)),
                    "time_to_recover": self.time_to_recover,
                    "recovered_at": self.recovered_at,
                    "transitions": list(self.transitions[-10:])}


def _iso(ts):
    import datetime
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ExternalProbe(threading.Thread):
    """Independent probe loop. Own Transport, own thread, own stop event."""

    def __init__(self, url, interval=1.0, timeout=2.0, tcp_host=None, tcp_port=None,
                 connect_ip=None, use_cache_buster=True, state_machine=None,
                 on_transition=None, max_samples=900):
        threading.Thread.__init__(self, daemon=True, name="galardo-external-probe")
        self.url = url
        self.interval = interval
        self.timeout = timeout
        parts = urlsplit(url)
        self.tcp_host = tcp_host or parts.hostname
        self.tcp_port = tcp_port or parts.port or (443 if parts.scheme == "https" else 80)
        self.connect_ip = connect_ip
        self.use_cache_buster = use_cache_buster
        self.state_machine = state_machine or DownStateMachine(on_transition=on_transition)
        self.transport = transport_mod.Transport(timeout=timeout, max_idle=4)
        self.stop_event = threading.Event()
        self.samples = []
        self.lock = threading.Lock()
        self.started_at = None
        self._tick = 0

    def _busted_url(self):
        if not self.use_cache_buster:
            return self.url
        parts = urlsplit(self.url)
        path = cache_buster_path(parts.path or "/", key=DEFAULT_NONCE_KEY)
        url = "%s://%s%s" % (parts.scheme, parts.netloc, path)
        if parts.query:
            url += "&" + parts.query
        return url

    def run(self):
        self.started_at = time.time()
        while not self.stop_event.is_set():
            self._tick += 1
            self._record(probe_http(self._busted_url(), timeout=self.timeout,
                                    connect_ip=self.connect_ip, transport=self.transport))
            if self.tcp_host and self._tick % 2 == 0:
                self._record(probe_tcp(self.tcp_host, self.tcp_port,
                                       timeout=min(1.5, self.timeout)))
            self.stop_event.wait(self.interval)

    def _record(self, sample):
        with self.lock:
            self.samples.append(sample)
            self.samples[:] = self.samples[-self.max_samples:]
        self.state_machine.feed(sample)

    def stop(self):
        self.stop_event.set()

    def close(self):
        self.stop()
        try:
            self.transport.close()
        except Exception:
            pass

    def error_ratio(self, window_seconds=30.0):
        cutoff = time.time() - window_seconds
        with self.lock:
            recent = [s for s in self.samples if s.ts >= cutoff]
        if not recent:
            return 0.0
        return 100.0 * sum(1 for s in recent if not s.ok) / float(len(recent))

    def snapshot(self):
        snap = self.state_machine.snapshot()
        snap["error_ratio_pct"] = round(self.error_ratio(), 2)
        snap["samples_total"] = len(self.samples)
        snap["url"] = self.url
        return snap


class DownWatcher(object):
    """Facade: owns probe + state machine, produces the DOWN verdict for evidence."""

    def __init__(self, url, interval=1.0, timeout=2.0, connect_ip=None,
                 failure_threshold=5, min_down_seconds=10.0,
                 recover_threshold=3, recover_seconds=5.0, on_transition=None):
        self.sm = DownStateMachine(failure_threshold=failure_threshold,
                                   min_down_seconds=min_down_seconds,
                                   recover_threshold=recover_threshold,
                                   recover_seconds=recover_seconds,
                                   on_transition=on_transition)
        self.probe = ExternalProbe(url, interval=interval, timeout=timeout,
                                   connect_ip=connect_ip, state_machine=self.sm)

    def start(self):
        self.probe.start()
        return self

    def stop(self):
        self.probe.close()

    def verdict(self):
        snap = self.probe.snapshot()
        snap["down_verified"] = snap["state"] in (STATE_DOWN, STATE_RECOVERING, STATE_RECOVERED)
        snap["scope"] = "LOKAL"
        return snap

    def evidence(self):
        return {"verdict": self.verdict(),
                "down_since": self.sm.down_since,
                "time_to_recover": self.sm.time_to_recover,
                "transitions": list(self.sm.transitions),
                "criteria": {"failure_threshold": self.sm.failure_threshold,
                             "min_down_seconds": self.sm.min_down_seconds,
                             "recover_threshold": self.sm.recover_threshold,
                             "recover_seconds": self.sm.recover_seconds}}
