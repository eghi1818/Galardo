"""GALARDO - minimal NATS client (stdlib TCP, text protocol v0).

Supports CONNECT/SUB/PUB/PING/PONG/MSG. Optional dependency: the fleet works
fully over HTTP polling; NATS is a transport upgrade for instant dispatch and
abort fanout. Set GALARDO_NATS_URL=nats://127.0.0.1:4222 to enable.
"""
import json
import socket
import threading
import time


class NatsError(Exception):
    pass


class NatsClient:
    def __init__(self, url="nats://127.0.0.1:4222", name="galardo-node"):
        self.url = url
        self.name = name
        self.sock = None
        self.subs = {}  # sid -> (subject, callback)
        self.sid = 0
        self.lock = threading.Lock()
        self.running = False
        self.reader = None
        self.connected = False

    def _connect_tcp(self):
        u = self.url.replace("nats://", "")
        host, _, port = u.partition(":")
        self.sock = socket.create_connection((host, int(port or 4222)), timeout=5)
        self.sock.settimeout(0.5)

    def connect(self):
        self._connect_tcp()
        buf = b""
        while b"INFO " not in buf:  # server greets with INFO
            chunk = self.sock.recv(65536)
            if not chunk:
                raise NatsError("no INFO from server")
            buf += chunk
        info = json.loads(buf.split(b"INFO ", 1)[1].split(b"\r\n", 1)[0])
        connect_msg = {"verbose": False, "pedantic": False, "tls_required": False,
                       "name": self.name, "lang": "galardo", "version": "1.0", "protocol": 1}
        self._send(("CONNECT " + json.dumps(connect_msg) + "\r\n").encode())
        self._send(b"PING\r\n")
        pong = self._read_line()
        if not pong.startswith(b"PONG"):
            raise NatsError(f"expected PONG, got {pong[:40]}")
        self.connected = True
        self.running = True
        self.reader = threading.Thread(target=self._read_loop, daemon=True,
                                       name=f"nats-reader-{self.name}")
        self.reader.start()
        return info

    def _send(self, data):
        with self.lock:
            self.sock.sendall(data)

    def _read_line(self):
        line = b""
        while not line.endswith(b"\r\n"):
            ch = self.sock.recv(1)
            if not ch:
                raise NatsError("connection closed")
            line += ch
        return line.strip()

    def _read_loop(self):
        buffer = b""
        while self.running:
            try:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buffer += chunk
            except socket.timeout:
                continue
            except OSError:
                break
            while True:
                if buffer.startswith(b"PING"):
                    try:
                        self._send(b"PONG\r\n")
                    except OSError:
                        return
                    buffer = buffer[5:]
                    continue
                if not buffer.startswith(b"MSG "):
                    break
                try:
                    head, rest = buffer.split(b"\r\n", 1)
                    parts = head.split(b" ")
                    subject, sid = parts[1].decode(), int(parts[2])
                    if len(parts) == 5:  # subject sid reply_to size
                        size = int(parts[4])
                    else:                # subject sid size
                        size = int(parts[3])
                    if len(rest) < size + 2:
                        break  # wait for more bytes
                    payload = rest[:size]
                    buffer = rest[size + 2:]
                    cb = self.subs.get(sid)
                    if cb:
                        try:
                            cb(subject, payload)
                        except Exception:
                            pass
                except Exception:
                    break
        self.connected = False

    def subscribe(self, subject, callback):
        with self.lock:
            self.sid += 1
            sid = self.sid
            self.subs[sid] = callback
        self._send(f"SUB {subject} {sid}\r\n".encode())
        return sid

    def publish(self, subject, payload):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload).encode()
        elif isinstance(payload, str):
            payload = payload.encode()
        self._send(f"PUB {subject} {len(payload)}\r\n".encode() + payload + b"\r\n")

    def drain(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.connected = False


def try_connect(url=None, name="galardo-node"):
    """Return connected client or None (transport falls back to HTTP)."""
    import os
    url = url or os.environ.get("GALARDO_NATS_URL")
    if not url:
        return None
    try:
        c = NatsClient(url, name=name)
        c.connect()
        return c
    except Exception:
        return None
