"""GALARDO - Identity Simulation (direct-to-origin, synthetic identities).

Purpose (PRD Addendum: Edge Client Simulation): stress-test INTERNAL modules of
an owner-controlled origin - CF-Connecting-IP parsing, LB hashing, session
tables, socket allocation - against 10K heterogeneous client identities.

Hard boundaries (locked in PRD addendum §4):
- identities are HEADER-LEVEL values only (CF-Connecting-IP / X-Forwarded-For),
  never packet-level spoofing; actual TCP source = registered worker VM
- no third-party/residential proxies, no IP rotation services
- pools are generated deterministically from a seed (reproducible evidence)
"""
import ipaddress
import json

from util import sha256_text

BUCKETS = 64  # hash buckets for distribution visualization
MAX_POOL = 50000

DEFAULT_CIDRS = [
    # Broad, realistic-looking spread for header-level identity variation.
    # These are header VALUES (not packet sources); targets are owner-internal.
    "23.0.0.0/12", "45.0.0.0/12", "66.0.0.0/12", "77.0.0.0/12",
    "89.0.0.0/12", "103.0.0.0/12", "114.0.0.0/12", "125.0.0.0/12",
    "146.0.0.0/12", "158.0.0.0/12", "170.0.0.0/12", "182.0.0.0/12",
    "194.0.0.0/12", "201.0.0.0/12", "212.0.0.0/12", "223.0.0.0/12",
]

UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 13; SM-A536E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]


def _cidr_hosts(cidr, rng, n):
    net = ipaddress.ip_network(cidr, strict=False)
    start = int(net.network_address)
    end = int(net.broadcast_address)
    span = end - start - 2
    if span <= 0:
        return []
    out = []
    for _ in range(n):
        out.append(str(ipaddress.ip_address(start + 2 + (rng.randrange(span)))))
    return out


def generate_identities(count, seed, cidrs=None):
    """Deterministic identity pool: same seed+count -> same pool on every worker."""
    rng_seed = f"{seed}:{count}"
    # derive a stable int seed from text seed
    s = int(sha256_text(rng_seed)[:16], 16)
    import random
    rng = random.Random(s)
    cidrs = cidrs or DEFAULT_CIDRS
    per = count // len(cidrs) + 1
    ips = []
    for c in cidrs:
        if len(ips) >= count:
            break
        ips.extend(_cidr_hosts(c, rng, per))
    ips = ips[:count]
    out = []
    for i, ip in enumerate(ips):
        out.append({
            "idx": i,
            "ip": ip,
            "session": f"sess-{s % 100000:05d}-{i:06d}",
            "ua": UAS[i % len(UAS)],
        })
    return out


def bucket_of(ip):
    """Distribution bucket: stable hash of full identity IP -> BUCKETS."""
    return int(sha256_text(ip)[:8], 16) % BUCKETS


def headers_for(ident, header="CF-Connecting-IP", path="edge"):
    """Header set per simulation path:
    - 'direct': CF-Connecting-IP + X-Forwarded-For (valid ONLY direct-to-origin;
      Cloudflare edge rejects spoofed CF-Connecting-IP with 403 — by design).
    - 'edge':   X-Client-Id / X-Session-Id carry the identity; edge-safe."""
    h = {"User-Agent": ident["ua"], "X-Session-Id": ident["session"]}
    if path == "direct":
        h["CF-Connecting-IP"] = ident["ip"]
        h["X-Forwarded-For"] = ident["ip"]
    else:
        h["X-Client-Id"] = ident["ip"]
    return h


def entropy(counts):
    """Shannon entropy of bucket distribution, normalized 0..1 (1 = uniform)."""
    total = sum(counts)
    if not total:
        return 0.0
    import math
    e = 0.0
    for c in counts:
        if c:
            p = c / total
            e -= p * math.log2(p)
    return round(e / math.log2(len(counts)), 4) if len(counts) > 1 else 0.0


def pool_meta(count, seed):
    """Compact pool descriptor for envelopes (deterministic regeneration)."""
    return {"count": count, "seed": seed, "buckets": BUCKETS,
            "pool_sha256": sha256_text(json.dumps({"count": count, "seed": seed},
                                                  sort_keys=True))}


def validate_identity_spec(spec, max_identities=None):
    """Server-side validation of scenario.identity_sim. Returns (ok, errors, normalized)."""
    errs = []
    enabled = bool(spec.get("enabled"))
    norm = {"enabled": enabled, "count": 0, "churn": "per-iteration",
            "header": "CF-Connecting-IP", "path": "edge", "seed": None}
    if not enabled:
        return True, [], norm
    count = spec.get("count")
    if not isinstance(count, int) or not (1 <= count <= MAX_POOL):
        errs.append({"field": "identity_sim.count", "code": "invalid",
                     "message": f"identity count must be 1..{MAX_POOL}"})
    else:
        if max_identities is not None and count > max_identities:
            errs.append({"field": "identity_sim.count", "code": "over_limit",
                         "message": f"identity count {count} exceeds policy cap {max_identities}"})
        norm["count"] = count
    path = spec.get("path", "edge")
    if path not in ("edge", "direct"):
        errs.append({"field": "identity_sim.path", "code": "invalid",
                     "message": "path must be 'edge' (X-Client-Id via CF) or 'direct' (CF-Connecting-IP to origin)"})
    else:
        norm["path"] = path
    churn = spec.get("churn", "per-iteration")
    if churn not in ("per-iteration", "per-vu"):
        errs.append({"field": "identity_sim.churn", "code": "invalid",
                     "message": "churn must be 'per-iteration' or 'per-vu'"})
    else:
        norm["churn"] = churn
    header = spec.get("header", "CF-Connecting-IP")
    if header not in ("CF-Connecting-IP", "X-Forwarded-For"):
        errs.append({"field": "identity_sim.header", "code": "invalid",
                     "message": "header must be 'CF-Connecting-IP' or 'X-Forwarded-For'"})
    else:
        norm["header"] = header
    seed = spec.get("seed")
    if seed is not None and (not isinstance(seed, str) or not (4 <= len(seed) <= 64)):
        errs.append({"field": "identity_sim.seed", "code": "invalid",
                     "message": "seed must be a string 4..64 chars"})
    else:
        norm["seed"] = seed or "default-seed"
    return (not errs), errs, norm
