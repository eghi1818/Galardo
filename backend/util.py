"""GALARDO - shared utilities."""
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def now_ts():
    return datetime.now(timezone.utc).timestamp()


def gen_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def gen_correlation_id():
    return uuid.uuid4().hex


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def parse_origin(origin):
    """Parse canonical origin -> (scheme, host, port). MVP: http/https only."""
    m = re.match(r"^(http|https)://([A-Za-z0-9._-]+)(?::(\d+))?$", origin or "")
    if not m:
        return None
    scheme, host, port = m.group(1), m.group(2), m.group(3)
    port = int(port) if port else (443 if scheme == "https" else 80)
    return scheme, host, port


def valid_iso_window(valid_from, valid_until):
    try:
        f = datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
        u = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
        return f < u
    except Exception:
        return False


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
