"""HTTP transport: connect-to-IP, keep-alive pooling, body encodings.

The point of this module is the ``connect()`` override. Galardo must be able
to talk to a *specific origin IP* while keeping the ``Host`` header and the
TLS SNI / certificate check pinned to the *domain name*. Without that, origin
discovery is guesswork: you cannot tell whether a hostname resolved to a CDN
edge or to the real backend.

Python 3.9 compatible.
"""

from __future__ import annotations

import base64
import gzip
import http.client
import io
import socket
import ssl
import threading
import time
from urllib.parse import urljoin, urlsplit

try:
    from . import netssl as _ns
except ImportError:
    import netssl as _ns

__all__ = [
    "TransportError", "Response", "ConnectionPool", "Transport",
    "ConnectToIPHTTPConnection", "ConnectToIPHTTPSConnection",
    "encode_body", "decode_body", "estimate_request_bytes", "DEFAULT_USER_AGENT",
]

DEFAULT_USER_AGENT = "Galardo/1.0"
DEFAULT_TIMEOUT = 15.0
SUPPORTED_ENCODINGS = ("identity", "gzip", "base64", "base64+gzip")

class TransportError(Exception):
    """The request could not be completed at the socket level."""

class ConnectToIPHTTPConnection(http.client.HTTPConnection):
    """Plain HTTP connection that dials ``connect_ip`` but speaks ``host``."""

    def __init__(self, host, connect_ip, port=None, connect_port=None,
                 timeout=DEFAULT_TIMEOUT, source_address=None, blocksize=8192):
        http.client.HTTPConnection.__init__(
            self, host, port, timeout=timeout,
            source_address=source_address, blocksize=blocksize)
        self._connect_ip = connect_ip
        self._connect_port = connect_port if connect_port is not None else self.port

    def connect(self):
        self.sock = socket.create_connection(
            (self._connect_ip, self._connect_port), self.timeout, self.source_address)
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        if self._tunnel_host:
            self._tunnel()

class ConnectToIPHTTPSConnection(http.client.HTTPSConnection):
    """TLS connection that dials ``connect_ip`` but verifies ``host``.

    TCP goes to the override address; ``server_hostname`` stays the logical
    host, so SNI and certificate validation are unaffected.
    """

    def __init__(self, host, connect_ip, port=None, connect_port=None,
                 timeout=DEFAULT_TIMEOUT, source_address=None, context=None,
                 blocksize=8192):
        http.client.HTTPSConnection.__init__(
            self, host, port, timeout=timeout, source_address=source_address,
            context=context, blocksize=blocksize)
        self._connect_ip = connect_ip
        self._connect_port = connect_port if connect_port is not None else self.port

    def connect(self):
        sock = socket.create_connection(
            (self._connect_ip, self._connect_port), self.timeout, self.source_address)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
            sock = self.sock
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)

class Response(object):
    __slots__ = ("method", "url", "status", "reason", "headers", "body",
                 "elapsed_ms", "connect_ip", "bytes_sent", "bytes_received",
                 "error", "http_version", "started_at")

    def __init__(self, method=None, url=None, status=None, reason=None,
                 headers=None, body=None, elapsed_ms=None, connect_ip=None,
                 bytes_sent=0, bytes_received=0, error=None, http_version=None):
        self.method = method
        self.url = url
        self.status = status
        self.reason = reason
        self.headers = headers
        self.body = body
        self.elapsed_ms = elapsed_ms
        self.connect_ip = connect_ip
        self.bytes_sent = bytes_sent
        self.bytes_received = bytes_received
        self.error = error
        self.http_version = http_version
        self.started_at = time.time()

    @property
    def ok(self):
        return self.error is None and self.status is not None and 200 <= self.status < 400

    @property
    def text(self):
        return (self.body or b"").decode("utf-8", "replace")

    def header(self, name, default=None):
        for key, value in (self.headers or {}).items():
            if key.lower() == name.lower():
                return value
        return default

    def to_dict(self):
        return {
            "method": self.method,
            "url": self.url,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "connect_ip": self.connect_ip,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "error": self.error,
        }

    def __repr__(self):
        return "<Response %s %s status=%s error=%s>" % (
            self.method, self.url, self.status, self.error)

def encode_body(payload, encoding="identity"):
    """Return ``(bytes, encoding_used)``. ``payload`` may be str or bytes."""
    if payload is None:
        return None, "identity"
    raw = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
    if encoding in (None, "", "identity"):
        return raw, "identity"
    if encoding == "gzip":
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as handle:
            handle.write(raw)
        return buffer.getvalue(), "gzip"
    if encoding == "base64":
        return base64.b64encode(raw), "base64"
    if encoding == "base64+gzip":
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as handle:
            handle.write(raw)
        return base64.b64encode(buffer.getvalue()), "base64+gzip"
    raise TransportError("unsupported body_encoding: %r" % (encoding,))

def decode_body(payload, encoding="identity"):
    if payload is None:
        return b""
    raw = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
    if encoding in (None, "", "identity"):
        return raw
    if encoding == "base64":
        return base64.b64decode(raw)
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "base64+gzip":
        return gzip.decompress(base64.b64decode(raw))
    raise TransportError("unsupported body_encoding: %r" % (encoding,))

def estimate_request_bytes(method, path, headers, payload_len):
    """Approximate on-the-wire request size (defect D16).

    Counts the request line, every header we control, and the two headers
    http.client injects when absent (Host, Accept-Encoding). Labelled an
    estimate because http.client may reformat header casing.
    """
    lowered = set(str(k).lower() for k in headers)
    head = "%s %s HTTP/1.1\r\n" % (method, path)
    if "host" not in lowered:
        head += "Host: <injected>\r\n"
    if "accept-encoding" not in lowered:
        head += "Accept-Encoding: identity\r\n"
    for key, value in headers.items():
        head += "%s: %s\r\n" % (key, value)
    head += "\r\n"
    return len(head.encode("utf-8", "replace")) + payload_len

class ConnectionPool(object):
    """Keyed idle-connection cache. Thread safe."""

    def __init__(self, max_idle=16, idle_timeout=20.0, context=None, source_address=None):
        self.max_idle = max_idle
        self.idle_timeout = idle_timeout
        self.context = context
        self.source_address = source_address
        self._idle = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(scheme, host, port, connect_ip, proxy):
        return (scheme, host, port, connect_ip,
                (proxy[0], int(proxy[1])) if proxy else None)

    def acquire(self, scheme, host, port, connect_ip, proxy, timeout):
        """Returns ``(connection, reused)`` so the caller can retry once when a
        pooled socket turns out to have been closed by the peer."""
        cache_key = self.key(scheme, host, port, connect_ip, proxy)
        now = time.monotonic()
        with self._lock:
            bucket = self._idle.get(cache_key)
            while bucket:
                connection, stamp = bucket.pop()
                if now - stamp <= self.idle_timeout and connection.sock is not None:
                    return connection, True
                try:
                    connection.close()
                except Exception:
                    pass
        return self._new(scheme, host, port, connect_ip, proxy, timeout), False

    def release(self, cache_key, connection):
        with self._lock:
            bucket = self._idle.setdefault(cache_key, [])
            if len(bucket) < self.max_idle:
                bucket.append((connection, time.monotonic()))
                return
        try:
            connection.close()
        except Exception:
            pass

    def close_all(self):
        with self._lock:
            buckets = list(self._idle.values())
            self._idle = {}
        for bucket in buckets:
            for connection, _ in bucket:
                try:
                    connection.close()
                except Exception:
                    pass

    def _new(self, scheme, host, port, connect_ip, proxy, timeout):
        dial_ip = connect_ip
        dial_port = None
        if proxy:
            dial_ip = proxy[0]
            dial_port = int(proxy[1])
        if dial_ip is None:
            dial_ip = host
        if scheme == "https":
            connection = ConnectToIPHTTPSConnection(
                host, dial_ip, port=port, connect_port=dial_port,
                timeout=timeout, source_address=self.source_address,
                context=self.context)
        else:
            connection = ConnectToIPHTTPConnection(
                host, dial_ip, port=port, connect_port=dial_port,
                timeout=timeout, source_address=self.source_address)
        if proxy:
            connection.set_tunnel(host, port)
        return connection

class Transport(object):
    """Small HTTP client facade. One instance per worker is enough."""

    def __init__(self, verify_tls=True, timeout=DEFAULT_TIMEOUT, max_idle=16,
                 idle_timeout=20.0, user_agent=DEFAULT_USER_AGENT,
                 source_address=None, proxy=None, max_body_bytes=8 * 1024 * 1024):
        self.timeout = timeout
        self.user_agent = user_agent
        self.source_address = source_address
        self.proxy = proxy
        self.max_body_bytes = max_body_bytes
        self.verify_tls = verify_tls
        self._context = _ns.context()
        if not verify_tls:
            self._context.check_hostname = False
            self._context.verify_mode = ssl.CERT_NONE
        self._pool = ConnectionPool(
            max_idle=max_idle, idle_timeout=idle_timeout,
            context=self._context, source_address=source_address)
        self._lock = threading.Lock()
        self._counters = {
            "requests": 0, "errors": 0, "bytes_sent": 0, "bytes_received": 0,
        }

    def set_proxy(self, proxy):
        """``proxy`` is ``(host, port)`` or None. Affects later requests only."""
        self.proxy = proxy

    def stats(self):
        with self._lock:
            return dict(self._counters)

    def close(self):
        self._pool.close_all()

    def request(self, method, url, headers=None, body=None, body_encoding="identity",
                connect_ip=None, timeout=None, allow_redirects=False,
                max_redirects=5, proxy=None):
        method = str(method).upper()
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https"):
            raise TransportError("unsupported scheme: %r" % parsed.scheme)

        payload, used_encoding = encode_body(body, body_encoding)
        prepared = dict(headers or {})
        lowered = set(key.lower() for key in prepared)
        if "user-agent" not in lowered:
            prepared["User-Agent"] = self.user_agent
        if "connection" not in lowered:
            prepared["Connection"] = "keep-alive"
        if payload is not None and "content-length" not in lowered:
            prepared["Content-Length"] = str(len(payload))
        if used_encoding != "identity" and "content-encoding" not in lowered:
            prepared["Content-Encoding"] = used_encoding

        attempts = 0
        current_url = url
        current_method = method
        current_payload = payload
        current_headers = prepared
        current_ip = connect_ip

        while True:
            response = self._send(current_method, current_url, current_headers,
                                  current_payload, current_ip, timeout, proxy)
            if not allow_redirects or response.error:
                return response
            if response.status not in (301, 302, 303, 307, 308):
                return response
            location = response.header("location")
            if not location or attempts >= max_redirects:
                return response
            attempts += 1
            current_url = urljoin(current_url, location)
            current_ip = None
            if response.status in (301, 302, 303) and current_method not in ("GET", "HEAD"):
                current_method = "GET"
                current_payload = None
                for key in ("Content-Length", "content-length",
                            "Content-Encoding", "content-encoding"):
                    current_headers.pop(key, None)

    def _send(self, method, url, headers, payload, connect_ip, timeout, proxy):
        parsed = urlsplit(url)
        scheme = parsed.scheme
        host = parsed.hostname
        if not host:
            raise TransportError("url has no host: %s" % url)
        port = parsed.port or (443 if scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = path + "?" + parsed.query

        effective_proxy = proxy if proxy is not None else self.proxy
        cache_key = ConnectionPool.key(scheme, host, port, connect_ip, effective_proxy)
        sent_bytes = estimate_request_bytes(method, path, headers, len(payload or b""))

        for attempt in (0, 1):
            response = Response(method=method, url=url, connect_ip=connect_ip)
            response.bytes_sent = sent_bytes
            connection = None
            reusable = False
            reused = False
            started = time.monotonic()
            try:
                connection, reused = self._pool.acquire(
                    scheme, host, port, connect_ip, effective_proxy,
                    timeout or self.timeout)
                connection.request(method, path, body=payload, headers=headers)
                raw = connection.getresponse()
                data = raw.read(self.max_body_bytes + 1)
                if len(data) > self.max_body_bytes:
                    data = data[:self.max_body_bytes]
                    reusable = False
                else:
                    reusable = not raw.will_close
                response.status = raw.status
                response.reason = raw.reason
                response.headers = dict(raw.getheaders())
                response.http_version = raw.version
                response.body = data
                response.bytes_received = len(data)
            except Exception as exc:
                response.error = "%s: %s" % (type(exc).__name__, exc)
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass
                    connection = None
            finally:
                response.elapsed_ms = (time.monotonic() - started) * 1000.0
                if connection is not None:
                    if reusable:
                        self._pool.release(cache_key, connection)
                    else:
                        try:
                            connection.close()
                        except Exception:
                            pass

            # A pooled socket may have been closed by the peer after release.
            # Exactly one transparent retry, on a fresh connection.
            if response.error and reused and attempt == 0:
                continue

            with self._lock:
                self._counters["requests"] += 1
                self._counters["bytes_sent"] += response.bytes_sent or 0
                self._counters["bytes_received"] += response.bytes_received or 0
                if response.error:
                    self._counters["errors"] += 1
            return response
