"""GALARDO - bounded load engine (worker core).

Pure-stdlib HTTP stress engine: thread pool of virtual users, weighted request
mix, per-request timeout, RPS cap via token bucket, ramp profile, think time.
Every metric goes to the shared TelemetryRing; safety controller consumes the
same ring plus independent probe events (Technical Design §11).

Hard guarantees:
- max duration enforced independently of scenario completion
- abort event checked between every request
- metrics include status classes, errors, latency percentiles, VUs, bytes
"""
import itertools
import random
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from util import now_iso

try:
    from . import netssl as _ns
except ImportError:
    import netssl as _ns

try:
    from . import assertions as assertions_mod
    from . import transport as transport_mod
    from . import cachebuster as cachebuster_mod
except ImportError:
    import assertions as assertions_mod
    import transport as transport_mod
    import cachebuster as cachebuster_mod

# Larger implied context for SSL certificates (not used for http lab targets)
ssl_ctx = None
try:
    import ssl
    ssl_ctx = _ns.context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
except Exception:
    pass


class TelemetryRing:
    """In-memory ring buffer of second-bucketed aggregates."""

    def __init__(self, max_seconds=7200):
        self.max = max_seconds
        self.lock = threading.Lock()
        self.buckets = {}
        self.series = {}  # metric -> list[(ts, value)]
        self.last_data_ts = None  # freshness signal for safety controller
        self.assert_samples = []  # bounded ring of failed-assertion details
        self.assert_lock = threading.Lock()

    def _bucket(self, ts=None):
        ts = ts or time.time()
        sec = int(ts)
        with self.lock:
            b = self.buckets.setdefault(sec, {
                "requests": 0, "ok": 0, "err_4xx": 0, "err_5xx": 0,
                "timeouts": 0, "conn_errors": 0, "bytes_sent": 0, "bytes_recv": 0,
                "assert_hard": 0, "assert_soft": 0,
                "pay_requests": 0, "pay_err": 0,
                "lat_sum": 0.0, "lat_max": 0.0, "latencies": [],
            })
        return b

    def record(self, status=None, error=None, latency=0.0, sent=0, recv=0, ts=None,
               assert_hard=0, assert_soft=0, payload=False):
        b = self._bucket(ts)
        with self.lock:
            self.last_data_ts = time.time()
            b["assert_hard"] += assert_hard
            b["assert_soft"] += assert_soft
            b["requests"] += 1
            b["lat_sum"] += latency
            b["lat_max"] = max(b["lat_max"], latency)
            if len(b["latencies"]) < 512:
                b["latencies"].append(latency)
            b["bytes_sent"] += sent
            b["bytes_recv"] += recv
            if error == "timeout":
                b["timeouts"] += 1
            elif error == "conn":
                b["conn_errors"] += 1
            elif isinstance(status, int):
                if status < 400:
                    b["ok"] += 1
                elif status < 500:
                    b["err_4xx"] += 1
                else:
                    b["err_5xx"] += 1
            if payload:
                b["pay_requests"] += 1
                if error or (isinstance(status, int) and status >= 400):
                    b["pay_err"] += 1

    def vu_sample(self, vus):
        ts = time.time()
        with self.lock:
            self.series.setdefault("active_vus", []).append((ts, vus))
            cut = ts - self.max
            self.series["active_vus"] = [x for x in self.series["active_vus"] if x[0] >= cut]

    def record_assertions(self, report, req_name=None, max_samples=200):
        """Keep a bounded trace of failed assertions for the evidence bundle."""
        with self.assert_lock:
            for outcome in report.hard_failures + report.soft_failures:
                if len(self.assert_samples) >= max_samples:
                    break
                self.assert_samples.append({
                    "ts": now_iso(), "request": req_name, "type": outcome.type,
                    "severity": outcome.severity, "detail": outcome.detail,
                })

    def window(self, last_seconds):
        """Aggregate over the trailing window -> dict."""
        now = time.time()
        lo = now - float(last_seconds)   # D15: no 1s truncation drift
        agg = {"requests": 0, "ok": 0, "err_4xx": 0, "err_5xx": 0, "timeouts": 0,
               "conn_errors": 0, "bytes_sent": 0, "bytes_recv": 0,
               "assert_hard": 0, "assert_soft": 0,
               "pay_requests": 0, "pay_err": 0,
               "lat_sum": 0.0, "lat_max": 0.0, "latencies": []}
        with self.lock:
            for sec, b in self.buckets.items():
                if sec >= lo:
                    for k in ("requests", "ok", "err_4xx", "err_5xx", "timeouts",
                              "conn_errors", "bytes_sent", "bytes_recv",
                              "assert_hard", "assert_soft",
                              "pay_requests", "pay_err"):
                        agg[k] += b[k]
                    agg["lat_sum"] += b["lat_sum"]
                    agg["lat_max"] = max(agg["lat_max"], b["lat_max"])
                    if len(agg["latencies"]) < 4096 and b["latencies"]:
                        agg["latencies"].extend(b["latencies"][-64:])
        total = agg["requests"]
        lat_sorted = sorted(agg["latencies"])
        n = len(lat_sorted)

        def pct(p):
            if not n:
                return None
            i = min(n - 1, max(0, int(round(p / 100.0 * (n - 1)))))
            return round(lat_sorted[i] * 1000.0, 1)

        return {
            "window_seconds": last_seconds,
            "requests": total,
            "rps": round(total / max(1e-9, last_seconds), 2),
            "ok": agg["ok"],
            "err_4xx": agg["err_4xx"],
            "err_5xx": agg["err_5xx"],
            "timeouts": agg["timeouts"],
            "conn_errors": agg["conn_errors"],
            "error_pct": round(100.0 * (agg["err_4xx"] + agg["err_5xx"] + agg["timeouts"] + agg["conn_errors"]) / total, 2) if total else 0.0,
            "p50_ms": pct(50),
            "p95_ms": pct(95),
            "p99_ms": pct(99),
            "lat_max_ms": round(agg["lat_max"] * 1000.0, 1) if n else None,
            "bytes_sent": agg["bytes_sent"],
            "bytes_recv": agg["bytes_recv"],
            "bandwidth_bps": round((agg["bytes_sent"] + agg["bytes_recv"]) / max(1e-9, last_seconds), 1),
            "assert_hard_fail": agg["assert_hard"],
            "assert_soft_fail": agg["assert_soft"],
            "payload_requests": agg["pay_requests"],
            "payload_errors": agg["pay_err"],
            "payload_error_pct": round(100.0 * agg["pay_err"] / agg["pay_requests"], 2) if agg["pay_requests"] else 0.0,
            "assert_fail_pct": round(100.0 * (agg["assert_hard"] + agg["assert_soft"]) / total, 2) if total else 0.0,
        }

    def timeseries(self, last_seconds=120, step=2):
        """Downsample buckets -> series for charts."""
        now = int(time.time())
        out = []
        with self.lock:
            for sec in range(now - last_seconds, now + 1, step):
                agg = {"t": sec, "rps": 0, "p95": None, "err_pct": 0.0}
                n_req, n_err, lats = 0, 0, []
                for s2 in range(sec, sec + step):
                    b = self.buckets.get(s2)
                    if b:
                        n_req += b["requests"]
                        n_err += b["err_4xx"] + b["err_5xx"] + b["timeouts"] + b["conn_errors"]
                        lats.extend(b["latencies"][-32:])
                if n_req:
                    agg["rps"] = round(n_req / step, 2)
                    agg["err_pct"] = round(100.0 * n_err / n_req, 2)
                    if lats:
                        lats.sort()
                        agg["p95"] = round(lats[min(len(lats) - 1, int(0.95 * (len(lats) - 1)))] * 1000.0, 1)
                out.append(agg)
        return out


class TokenBucket:
    """Global RPS limiter shared by all VUs. Refills at `rate` tokens/sec,
    capacity 1s worth. Starts empty so the cap is strict from t=0."""

    def __init__(self, rate):
        self.rate = float(rate)
        self.tokens = 0.0
        self.last = time.time()
        self.lock = threading.Lock()

    def take(self, stop=None, max_wait=None):
        """Block until one token is available. Returns False if stop set or
        max_wait elapsed without a token."""
        deadline = time.time() + max_wait if max_wait else None
        while True:
            if stop is not None and stop.is_set():
                return False
            with self.lock:
                now = time.time()
                self.tokens = min(self.rate, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True
                wait = (1.0 - self.tokens) / self.rate
            if deadline and time.time() + wait > deadline:
                # one final non-blocking attempt before giving up
                with self.lock:
                    now = time.time()
                    self.tokens = min(self.rate, self.tokens + (now - self.last) * self.rate)
                    self.last = now
                    if self.tokens >= 1.0:
                        self.tokens -= 1.0
                        return True
                return False
            if stop is not None:
                stop.wait(min(wait, 0.25))
            else:
                time.sleep(min(wait, 0.25))


class LoadEngine:
    """Runs a bounded scenario against a single resolved origin."""

    def __init__(self, job_id, run_id, origin, normalized, effective, telemetry, abort_check,
                 on_event=None, connect_ip=None, verify_tls=True, lanes=None):
        self.job_id = job_id
        self.run_id = run_id
        self.origin = origin  # "http://host:port"
        self.connect_ip = connect_ip
        self.verify_tls = verify_tls
        self.lanes = list(lanes) if lanes else []
        self.lane_hits = {}
        self.lane_lock = threading.Lock()
        self.vu_transports = {}
        self.vu_errors = []
        self.keep_alive = normalized.get("keep_alive", True)
        self.transport = transport_mod.Transport(verify_tls=verify_tls)
        self.piercer = cachebuster_mod.Piercer(
            run_id=run_id, enabled=bool(normalized.get("cache_buster", True)))
        self.assert_fail_hard = 0
        self.assert_fail_soft = 0
        self.norm = normalized
        self.eff = effective  # dict with max_rps/max_vus/max_duration_sec/max_concurrency
        self.telemetry = telemetry
        self.abort_check = abort_check  # callable -> (should_abort: bool, reason: str)
        self.on_event = on_event
        self.stop = threading.Event()
        self.abort_reason = None
        self.threads = []
        self.started_at = None
        self.ended_at = None
        cap_rps = self.eff.get("max_rps")
        self.bucket = TokenBucket(cap_rps) if cap_rps else None

    # ---- request mix -----------------------------------------------------
    def _pick_request(self):
        reqs = self.norm["requests"]
        total = self.norm.get("total_weight") or sum(r["weight"] for r in reqs)
        x = random.uniform(0, total)
        acc = 0
        for r in reqs:
            acc += r["weight"]
            if x <= acc:
                return r
        return reqs[-1]

    def _do_request(self, req, tr=None):
        url = self.origin + urllib.parse.quote(req["path"], safe="/?&=%")
        q = req.get("query") or {}
        if q:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(q)
        headers = {"User-Agent": "galardo-worker/1.0 (bounded lab run)", "Accept": "*/*"}
        if not self.keep_alive:
            headers["Connection"] = "close"
        for k, v in (req.get("headers") or {}).items():
            headers[k] = str(v)
        # Goal 2: nonce unik agar CDN tidak melayani salinan cache
        if self.piercer.enabled:
            url, _gb_nonce = self.piercer.decorate(url)
            for _hk, _hv in cachebuster_mod.NO_CACHE_HEADERS.items():
                headers.setdefault(_hk, _hv)
        timeout = req.get("timeout_ms", 1000) / 1000.0
        t0 = time.time()
        resp = (tr or self.transport).request(
            req["method"], url, headers=headers,
            body=req.get("body"), body_encoding=req.get("body_encoding") or "identity",
            connect_ip=self.connect_ip, timeout=timeout)
        dt = time.time() - t0
        if self.piercer.enabled:
            try:
                self.piercer.observe(getattr(resp, "headers", None) or {}, url=url)
            except Exception:
                pass

        hard = soft = 0
        specs = req.get("assertions") or []
        if specs:
            report = assertions_mod.evaluate_all(specs, resp, elapsed_ms=dt)
            hard = len(report.hard_failures)
            soft = len(report.soft_failures)
            if hard or soft:
                self.telemetry.record_assertions(report, req.get("name"))
                self.assert_fail_hard += hard
                self.assert_fail_soft += soft

        is_payload = bool(req.get("body"))
        if resp.error:
            kind = "timeout" if "timeout" in resp.error.lower() else "conn"
            self.telemetry.record(error=kind, latency=dt,
                                  sent=resp.bytes_sent or 0, recv=resp.bytes_received or 0,
                                  assert_hard=hard, assert_soft=soft, payload=is_payload)
        else:
            self.telemetry.record(status=resp.status, latency=dt,
                                  sent=resp.bytes_sent or 0, recv=resp.bytes_received or 0,
                                  assert_hard=hard, assert_soft=soft, payload=is_payload)
        return resp

    # ---- multi-lane ------------------------------------------------------
    def _lane_for(self, vu_id):
        if not self.lanes:
            return None
        return self.lanes[vu_id % len(self.lanes)]

    @staticmethod
    def _lane_id(item, fallback="lane"):
        for attr in ("lane_id", "id", "name"):
            v = getattr(item, attr, None)
            if v:
                return str(v)
        if isinstance(item, dict) and item.get("lane_id"):
            return str(item["lane_id"])
        return fallback

    @staticmethod
    def _lane_endpoint(item):
        """(host, port) dari objek lane apa pun; None = jalur langsung."""
        if item is None:
            return None
        fn = getattr(item, "endpoint", None)
        if callable(fn):
            try:
                ep = fn()
            except Exception:
                ep = None
            if isinstance(ep, dict) and ep.get("host") and ep.get("port"):
                return (ep["host"], int(ep["port"]))
            if isinstance(ep, (list, tuple)) and len(ep) >= 2 and ep[0] and ep[1]:
                return (ep[0], int(ep[1]))
        if isinstance(item, dict):
            if item.get("host") and item.get("port"):
                return (item["host"], int(item["port"]))
            pr = item.get("proxy")
            if isinstance(pr, (list, tuple)) and len(pr) >= 2:
                return (pr[0], int(pr[1]))
        if isinstance(item, (list, tuple)) and len(item) >= 2 and item[0] and item[1]:
            return (item[0], int(item[1]))
        return None

    def _vu_transport(self, lane):
        """Transport per lane - tiap VU memakai transportnya sendiri (hindari balapan proxy)."""
        if lane is None:
            return self.transport
        lane_id = self._lane_id(lane)
        tr = self.vu_transports.get(lane_id)
        if tr is not None:
            return tr
        with self.lane_lock:
            tr = self.vu_transports.get(lane_id)
            if tr is not None:
                return tr
            tr = transport_mod.Transport(verify_tls=self.verify_tls)
            ep = self._lane_endpoint(lane)
            setter = getattr(tr, "set_proxy", None)
            if ep and callable(setter):
                try:
                    setter(ep[0], ep[1])
                except TypeError:
                    try:
                        setter(ep)
                    except Exception:
                        pass
                except Exception:
                    pass
            if not ep:
                self._start_lane(tr)
            self.vu_transports[lane_id] = tr
            self.lane_hits.setdefault(lane_id, 0)
            return tr

    def _start_lane(self, tr):
        """Nyalakan transport lane dengan CARA YANG SAMA seperti transport utama.

        Nama metode dicari dari transport utama (bukan ditebak), jadi kalau engine
        memakai start()/open()/warmup(), transport lane ikut memakai yang sama.
        """
        for nama in ("start", "open", "warmup", "connect"):
            utama = getattr(self.transport, nama, None)
            milik = getattr(tr, nama, None)
            if callable(utama) and callable(milik):
                try:
                    milik()
                except Exception:
                    pass
                return nama
        return None

    def _catat_lane(self, lane):
        if lane is None:
            return
        lid = self._lane_id(lane)
        with self.lane_lock:
            self.lane_hits[lid] = self.lane_hits.get(lid, 0) + 1

    def _vu_aman(self, vu_id, deadline):
        """Pembungkus VU: exception apa pun dicatat, TIDAK mati sunyi."""
        try:
            self._vu_loop(vu_id, deadline)
        except BaseException as exc:
            with self.lane_lock:
                if len(self.vu_errors) < 50:
                    self.vu_errors.append("vu%d: %r" % (vu_id, exc))

    # ---- worker loop -----------------------------------------------------
    def _vu_loop(self, vu_id, deadline):
        """VU loop: global token bucket enforces max_rps across all VUs;
        think time shapes per-VU concurrency; abort checked every iteration."""
        lane = self._lane_for(vu_id)
        tr = self._vu_transport(lane)
        self._catat_lane(lane)
        think_min = self.norm.get("think_time_ms", {}).get("min", 0) / 1000.0
        think_max = self.norm.get("think_time_ms", {}).get("max", 0) / 1000.0
        while not self.stop.is_set() and time.time() < deadline:
            should, reason = self.abort_check()
            if should:
                self.abort_reason = self.abort_reason or reason
                self.stop.set()
                break
            if self.bucket and not self.bucket.take(stop=self.stop,
                                                    max_wait=max(0.5, deadline - time.time())):
                if self.stop.is_set():
                    break
                continue  # token timeout; re-check abort/deadline
            self._do_request(self._pick_request(), tr)
            if think_max:
                self.stop.wait(random.uniform(think_min, think_max))

    # ---- ramp ------------------------------------------------------------
    def _ramp_vus_at(self, elapsed):
        ramp = self.norm["profile"].get("ramp") or []
        target = self.norm["profile"]["virtual_users"]
        best = 0
        for r in ramp:
            if elapsed >= r.get("after_seconds", 0):
                best = r.get("virtual_users", target)
        return min(best, target) if ramp else target

    def _controller(self, deadline):
        """Main controller: adjusts VU pool to ramp, samples VUs, enforces deadline."""
        cap_vus = self.eff.get("max_vus") or self.norm["profile"]["virtual_users"]
        cap_rps = self.eff.get("max_rps")
        active = {}
        tid = itertools.count()
        t0 = time.time()
        while not self.stop.is_set():
            if time.time() >= deadline:
                break
            elapsed = time.time() - t0
            want = self._ramp_vus_at(elapsed)
            # reconcile threads
            for k in list(active.keys()):
                if not active[k].is_alive():
                    del active[k]
            while len(active) < min(want, cap_vus) and not self.stop.is_set():
                th = threading.Thread(target=self._vu_aman,
                                      args=(next(tid), deadline), daemon=True)
                active[th.name] = th
                th.start()
            if len(active) > want:
                pass  # threads exit naturally; loop re-checks via abort/deadline
            self.telemetry.vu_sample(len(active))
            self.stop.wait(0.5)
        self.stop.set()

    # ---- lifecycle -------------------------------------------------------
    def run(self):
        cap_dur = self.eff.get("max_duration_sec") or self.norm["profile"]["duration_seconds"]
        duration = min(cap_dur, self.norm["profile"]["duration_seconds"])
        self.started_at = time.time()
        deadline = self.started_at + duration
        ctrl = threading.Thread(target=self._controller, args=(deadline,), daemon=True)
        ctrl.start()
        # deadline watchdog independent of controller
        while time.time() < deadline and not self.stop.is_set():
            self.stop.wait(0.2)
        self.stop.set()
        ctrl.join(timeout=5)
        time.sleep(1.0)  # brief drain window for in-flight requests
        self.ended_at = time.time()
        try:
            self.transport.close()
        except Exception:
            pass
        for _tr in list(self.vu_transports.values()):
            try:
                _tr.close()
            except Exception:
                pass
        return {"started_at": now_iso(), "duration_actual": round(self.ended_at - self.started_at, 2),
                "abort_reason": self.abort_reason,
                "assert_hard_fail": self.assert_fail_hard,
                "assert_soft_fail": self.assert_fail_soft,
                "cache": self.piercer.stats(),
                "lanes": ({"jumlah": len(self.lanes), "hits": dict(self.lane_hits)} if self.lanes else None),
                "vu_errors": list(self.vu_errors)[:5]}
