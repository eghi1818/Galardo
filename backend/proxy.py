"""GALARDO - lane proxy: jalur egress berlabel, rotasi opt-in, statistik terpisah.

Lane = jalur keluar trafik. Tiga macam:
  - "direct"      : tanpa proxy (DEFAULT; rotasi tidak memutus keep-alive)
  - "rotate"      : endpoint diambil dari pool yang berputar
  - "residential" : pool residensial, statistiknya dilaporkan terpisah dari target

Aturan yang dipegang modul ini (ROADMAP item 2/3/4):
  1. direct adalah default; rotasi hanya aktif bila diminta lewat set_mode().
  2. statistik lane TIDAK pernah dicampur dengan statistik target.
  3. setiap request lewat Transport diberi label lane (response.lane) supaya teraudit.

Tanpa kredensial, lane proxy jatuh ke koneksi langsung - integrasi bisa dibangun
sekarang dan diisi kapan pun pool dilanggani.

Python 3.9, stdlib saja.
"""
import os
import threading

import proxypool

DIRECT = "direct"
ROTATE = "rotate"
RESIDENTIAL = "residential"
MODES = (DIRECT, ROTATE, RESIDENTIAL)

ENV_ROTATE_POOL = "GALARDO_LANE_ROTATE_POOL"
ENV_RESIDENTIAL_POOL = "GALARDO_LANE_RESIDENTIAL_POOL"

STAT_KEYS = ("requests", "errors", "bytes_sent", "bytes_received", "elapsed_ms")


def _default_pool():
    """Nama pool default dari env; dipakai bila lane TIDAK diberi pool."""
    try:
        import os as _os
        return _os.environ.get("GALARDO_PROXY_POOL") or None
    except Exception:
        return None


class LaneError(ValueError):
    """Operasi lane tidak sah."""


def _pair(proxy):
    return (proxy[0], int(proxy[1])) if proxy else None


class Lane(object):
    """Satu jalur egress dengan counter sendiri (terpisah dari statistik target)."""

    def __init__(self, lane_id, kind, pool=None, proxy=None):
        if kind not in MODES:
            raise LaneError("kind lane tidak dikenal: %r" % (kind,))
        self.id = lane_id
        self.kind = kind
        self.pool = pool if pool is not None else _default_pool()
        self.proxy = _pair(proxy)
        self._lock = threading.Lock()
        self._c = dict((k, 0) for k in STAT_KEYS)

    def endpoint(self):
        """(host, port) untuk lane ini, atau None bila jalur langsung."""
        if self.proxy:
            return self.proxy
        if not self.pool:
            return None
        try:
            return _pair(proxypool.resolve(self.pool))
        except Exception:
            return None

    def evidence(self):
        """Label lane yang ditempelkan ke respons/evidence."""
        ep = self.endpoint()
        return {"lane_id": self.id, "lane_kind": self.kind,
                "egress": "proxy" if ep else "direct",
                "proxy": ("%s:%d" % ep) if ep else None,
                "pool": self.pool}

    def record(self, response):
        with self._lock:
            self._c["requests"] += 1
            self._c["bytes_sent"] += getattr(response, "bytes_sent", 0) or 0
            self._c["bytes_received"] += getattr(response, "bytes_received", 0) or 0
            self._c["elapsed_ms"] += getattr(response, "elapsed_ms", 0.0) or 0.0
            if getattr(response, "error", None):
                self._c["errors"] += 1

    def stats(self):
        with self._lock:
            d = dict(self._c)
        d.update({"id": self.id, "kind": self.kind,
                  "egress": "proxy" if self.endpoint() else "direct"})
        return d


class LaneRegistry(object):
    """Daftar lane + mode aktif. Default: satu lane "direct"."""

    def __init__(self, mode=DIRECT):
        self._lock = threading.Lock()
        self._lanes = {}
        self._mode = None
        self.add(Lane(DIRECT, DIRECT))
        if os.environ.get(ENV_ROTATE_POOL):
            self.add(Lane(ROTATE, ROTATE, pool=os.environ[ENV_ROTATE_POOL]))
        if os.environ.get(ENV_RESIDENTIAL_POOL):
            self.add(Lane(RESIDENTIAL, RESIDENTIAL,
                          pool=os.environ[ENV_RESIDENTIAL_POOL]))
        self.set_mode(mode)

    def add(self, lane):
        if not isinstance(lane, Lane):
            raise LaneError("bukan Lane: %r" % (lane,))
        with self._lock:
            self._lanes[lane.id] = lane
        return lane

    def add_lane(self, lane_id, kind=DIRECT, pool=None, proxy=None):
        return self.add(Lane(lane_id, kind, pool=pool, proxy=proxy))

    def get(self, lane_id):
        try:
            return self._lanes[lane_id]
        except KeyError:
            raise LaneError("lane tidak ada: %r" % (lane_id,))

    def lanes(self):
        with self._lock:
            return sorted(self._lanes)

    @property
    def mode(self):
        return self._mode

    def set_mode(self, mode):
        if mode not in MODES:
            raise LaneError("mode tidak dikenal: %r" % (mode,))
        if mode not in self._lanes:
            raise LaneError("lane %r belum terdaftar" % (mode,))
        with self._lock:
            self._mode = mode
        return mode

    def current(self):
        return self.get(self._mode)

    def match(self, proxy):
        """Lane yang bertanggung jawab atas endpoint proxy yang sedang dipakai."""
        if proxy is None:
            return self._lanes.get(DIRECT)
        p = _pair(proxy)
        for lane in self._lanes.values():
            if lane.endpoint() == p:
                return lane
        cur = self._lanes.get(self._mode)
        if cur is not None and cur.endpoint() == p:
            return cur
        return None

    def status(self, target=None):
        """Statistik per lane, dipisah dari statistik target."""
        return {"mode": self._mode,
                "lanes": dict((lid, self._lanes[lid].stats()) for lid in self.lanes()),
                "target": dict(target) if target is not None else None}


def attach(transport, registry=None):
    """Pasang registry lane pada transport. Transport tanpa registry = tanpa label."""
    reg = registry or REGISTRY
    transport.lanes = reg
    return reg


def send(transport, method, url, lane_id=None, **kw):
    """Kirim request lewat lane aktif (atau lane_id eksplisit) dengan label lane."""
    reg = getattr(transport, "lanes", None) or REGISTRY
    lane = reg.get(lane_id) if lane_id else reg.current()
    return transport.request(method, url, proxy=lane.endpoint(), **kw)


def status(target=None):
    return REGISTRY.status(target=target)


def reset():
    global REGISTRY
    REGISTRY = LaneRegistry()
    return REGISTRY


REGISTRY = LaneRegistry()
