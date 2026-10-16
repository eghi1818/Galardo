"""GALARDO - Scenario engine (Technical Design §5).

Pipeline: YAML -> bounded parse -> strict schema -> canonical normalize ->
target-scope validation -> policy intersection -> immutable version (sha256).

- Rejects unknown fields (additionalProperties=false semantics).
- Rejects absolute URLs, non-allowlisted methods, oversized payloads,
  deep/large YAML documents.
- target_ref resolved server-side to an authorized target; the worker never
  receives a free-form base URL.
"""
import json

import yaml

from util import sha256_text, parse_origin

MAX_YAML_BYTES = 65536
MAX_DEPTH = 12
ALLOWED_METHODS = {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}
TOP_LEVEL = {"proxy_pool", "schema_version", "name", "description", "target_ref", "profile",
             "requests", "think_time_ms", "identity_sim", "keep_alive", "cache_buster"}
PROFILE_FIELDS = {"duration_seconds", "virtual_users", "max_rps", "max_concurrency", "ramp"}
REQUEST_FIELDS = {"name", "method", "path", "weight", "timeout_ms", "headers", "query",
                 "body", "body_encoding", "assertions"}
RAMP_FIELDS = {"after_seconds", "virtual_users"}
MAX_BODY_BYTES = 1048576
ALLOWED_BODY_ENCODINGS = {"identity", "gzip", "base64", "base64+gzip"}


class ScenarioError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"scenario invalid: {len(errors)} error(s)")


def _depth(obj, d=0):
    if d > MAX_DEPTH:
        return d
    if isinstance(obj, dict):
        return max([_depth(v, d + 1) for v in obj.values()] or [d])
    if isinstance(obj, list):
        return max([_depth(v, d + 1) for v in obj] or [d])
    return d


def _reject_unknown(fields, allowed, prefix, errors):
    for f in fields:
        if f not in allowed:
            errors.append({"field": f"{prefix}{f}", "code": "unknown_field",
                           "message": f"Unknown field '{prefix}{f}' (additionalProperties=false)"})


def parse_scenario_yaml(yaml_text, targets_by_name):
    """Parse + validate. targets_by_name maps target_ref name -> target doc.
    Returns normalized dict (no ids yet). Raises ScenarioError with field errors."""
    errors = []
    if not isinstance(yaml_text, str) or not yaml_text.strip():
        raise ScenarioError([{"field": "yaml", "code": "empty", "message": "Scenario YAML is empty"}])
    if len(yaml_text.encode("utf-8")) > MAX_YAML_BYTES:
        errors.append({"field": "yaml", "code": "too_large",
                       "message": f"Scenario exceeds {MAX_YAML_BYTES} bytes limit"})
        raise ScenarioError(errors)

    try:
        doc = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ScenarioError([{"field": "yaml", "code": "parse_error", "message": str(e)[:300]}])
    if not isinstance(doc, dict):
        raise ScenarioError([{"field": "yaml", "code": "schema", "message": "Root must be a mapping"}])
    if _depth(doc) > MAX_DEPTH:
        raise ScenarioError([{"field": "yaml", "code": "too_deep",
                              "message": f"Nesting exceeds {MAX_DEPTH} levels"}])

    _reject_unknown(set(doc.keys()), TOP_LEVEL, "", errors)

    pp = doc.get("proxy_pool")
    if pp is not None:
        if isinstance(pp, str):
            if not pp.strip():
                errors.append({"field": "proxy_pool", "code": "invalid_proxy_pool",
                               "message": "proxy_pool must be a non-empty string"})
        elif isinstance(pp, list):
            if not pp or not all(isinstance(x, str) and x.strip() for x in pp):
                errors.append({"field": "proxy_pool", "code": "invalid_proxy_pool",
                               "message": "proxy_pool list must contain non-empty strings"})
        else:
            errors.append({"field": "proxy_pool", "code": "invalid_proxy_pool",
                           "message": "proxy_pool must be a string or a list of strings"})

    cb_on = doc.get("cache_buster")
    if cb_on is not None and not isinstance(cb_on, bool):
        errors.append({"field": "cache_buster", "code": "invalid",
                       "message": "cache_buster must be a boolean"})

    schema_version = doc.get("schema_version")
    if schema_version not in ("1.0", "1.1", "1.2"):
        errors.append({"field": "schema_version", "code": "unsupported",
                       "message": "schema_version must be '1.0', '1.1' or '1.2'"})
    name = doc.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 80):
        errors.append({"field": "name", "code": "required", "message": "name required (1..80 chars)"})

    # target_ref must resolve server-side
    target_ref = doc.get("target_ref")
    target = targets_by_name.get(target_ref) if isinstance(target_ref, str) else None
    if target is None:
        errors.append({"field": "target_ref", "code": "unresolved",
                       "message": f"target_ref '{target_ref}' does not resolve to an authorized target"})

    profile = doc.get("profile") or {}
    if not isinstance(profile, dict):
        errors.append({"field": "profile", "code": "schema", "message": "profile must be a mapping"})
        profile = {}
    _reject_unknown(set(profile.keys()), PROFILE_FIELDS, "profile.", errors)
    for f in ("duration_seconds", "virtual_users", "max_rps"):
        v = profile.get(f)
        if not isinstance(v, int) or v < 1:
            errors.append({"field": f"profile.{f}", "code": "invalid",
                           "message": f"profile.{f} must be a positive integer"})
    ramp = profile.get("ramp") or []
    if ramp:
        if not isinstance(ramp, list):
            errors.append({"field": "profile.ramp", "code": "schema", "message": "ramp must be a list"})
        for i, r in enumerate(ramp):
            if not isinstance(r, dict):
                errors.append({"field": f"profile.ramp[{i}]", "code": "schema", "message": "ramp entry must be a mapping"})
            else:
                _reject_unknown(set(r.keys()), RAMP_FIELDS, f"profile.ramp[{i}].", errors)

    requests = doc.get("requests") or []
    if not isinstance(requests, list) or not requests:
        errors.append({"field": "requests", "code": "required", "message": "at least one request required"})
        requests = []
    paths = []
    total_weight = 0
    for i, r in enumerate(requests):
        if not isinstance(r, dict):
            errors.append({"field": f"requests[{i}]", "code": "schema", "message": "request must be a mapping"})
            continue
        _reject_unknown(set(r.keys()), REQUEST_FIELDS, f"requests[{i}].", errors)
        method = (r.get("method") or "GET").upper()
        if method not in ALLOWED_METHODS:
            errors.append({"field": f"requests[{i}].method", "code": "method_not_allowed",
                           "message": f"Method {method} not allowed (allowed: {sorted(ALLOWED_METHODS)}). "
                                      f"Active mode: state-changing methods are executed and verified."})
        path = r.get("path") or "/"
        if not isinstance(path, str) or not path.startswith("/"):
            errors.append({"field": f"requests[{i}].path", "code": "invalid_path",
                           "message": "path must start with '/' (relative paths only)"})
        elif "://" in path:
            errors.append({"field": f"requests[{i}].path", "code": "absolute_url",
                           "message": "Absolute URLs are forbidden in scenario requests"})
        else:
            paths.append(path)
        w = r.get("weight", 100)
        if not isinstance(w, int) or w < 1:
            errors.append({"field": f"requests[{i}].weight", "code": "invalid",
                           "message": "weight must be a positive integer"})
        else:
            total_weight += w
        t = r.get("timeout_ms", 1000)
        if not isinstance(t, int) or not (1 <= t <= 30000):
            errors.append({"field": f"requests[{i}].timeout_ms", "code": "invalid",
                           "message": "timeout_ms must be 1..30000"})
        hdrs = r.get("headers") or {}
        if not isinstance(hdrs, dict):
            errors.append({"field": f"requests[{i}].headers", "code": "schema", "message": "headers must be a mapping"})
        else:
            for hk in hdrs:
                if hk.lower() in ("cookie", "authorization", "set-cookie", "proxy-authorization"):
                    errors.append({"field": f"requests[{i}].headers.{hk}", "code": "sensitive_header",
                                   "message": f"Header '{hk}' is forbidden in scenarios (secret hygiene)"})
        body = r.get("body")
        if body is not None:
            if not isinstance(body, str):
                errors.append({"field": f"requests[{i}].body", "code": "schema",
                               "message": "body must be a string"})
            elif len(body.encode("utf-8")) > MAX_BODY_BYTES:
                errors.append({"field": f"requests[{i}].body", "code": "too_large",
                               "message": f"body exceeds {MAX_BODY_BYTES} bytes"})
        enc = r.get("body_encoding")
        if enc is not None:
            if enc not in ALLOWED_BODY_ENCODINGS:
                errors.append({"field": f"requests[{i}].body_encoding", "code": "invalid",
                               "message": f"body_encoding must be one of {sorted(ALLOWED_BODY_ENCODINGS)}"})
            elif body is None:
                errors.append({"field": f"requests[{i}].body_encoding", "code": "invalid",
                               "message": "body_encoding requires body"})
        specs = r.get("assertions")
        if specs is not None:
            if not isinstance(specs, list):
                errors.append({"field": f"requests[{i}].assertions", "code": "schema",
                               "message": "assertions must be a list"})
            else:
                for j, spec in enumerate(specs):
                    if not isinstance(spec, (dict, str)):
                        errors.append({"field": f"requests[{i}].assertions[{j}]", "code": "schema",
                                       "message": "each assertion must be a mapping or a string"})
                    elif isinstance(spec, dict) and not spec.get("type"):
                        errors.append({"field": f"requests[{i}].assertions[{j}].type", "code": "required",
                                       "message": "assertion requires a type"})

    identity_spec = doc.get("identity_sim") or {}
    if not isinstance(identity_spec, dict):
        errors.append({"field": "identity_sim", "code": "schema",
                       "message": "identity_sim must be a mapping"})
        identity_spec = {}
    try:
        import identity_sim as _isim
        _ok, ierrs, _inorm = _isim.validate_identity_spec(identity_spec)
        errors.extend(ierrs)
    except Exception as _e:
        errors.append({"field": "identity_sim", "code": "internal", "message": str(_e)[:120]})

    think = doc.get("think_time_ms") or {}
    if not isinstance(think, dict):
        errors.append({"field": "think_time_ms", "code": "schema", "message": "think_time_ms must be a mapping"})
        think = {}
    tmin, tmax = think.get("min", 0), think.get("max", 0)
    if not isinstance(tmin, int) or tmin < 0 or not isinstance(tmax, int) or tmax < tmin:
        errors.append({"field": "think_time_ms", "code": "invalid",
                       "message": "think_time_ms requires integers min <= max"})

    if errors:
        raise ScenarioError(errors)

    normalized = {
        "schema_version": schema_version,
        "name": name,
        "description": doc.get("description", ""),
        "target_ref": target_ref,
        "target_id": target["id"],
        "target_origin": target["canonical_origin"],
        "profile": {
            "duration_seconds": profile["duration_seconds"],
            "virtual_users": profile["virtual_users"],
            "max_rps": profile["max_rps"],
            "max_concurrency": profile.get("max_concurrency"),
            "ramp": ramp,
        },
        "requests": [
            {
                "name": r.get("name", f"req-{i+1}"),
                "method": (r.get("method") or "GET").upper(),
                "path": r.get("path") or "/",
                "weight": r.get("weight", 100),
                "timeout_ms": r.get("timeout_ms", 1000),
                "headers": r.get("headers") or {},
                "query": r.get("query") or {},
                "body": r.get("body"),
                "body_encoding": r.get("body_encoding") or "identity",
                "assertions": r.get("assertions") or [],
            }
            for i, r in enumerate(requests)
        ],
        "request_paths": paths,
        "total_weight": total_weight,
        "think_time_ms": {"min": tmin, "max": tmax},
    }
    # keep_alive (Improvement A1): absent = engine default; true = force keep-alive
    # meski identity_sim churn aktif (untuk memisahkan penyebab kegagalan).
    ka = doc.get("keep_alive")
    if ka is not None:
        if not isinstance(ka, bool):
            errors.append({"field": "keep_alive", "code": "invalid",
                           "message": "keep_alive must be a boolean"})
        else:
            normalized["keep_alive"] = ka
    # cache_buster (Goal 2): default ON. false hanya untuk pembanding.
    normalized["cache_buster"] = True if cb_on is None else bool(cb_on)
    if schema_version in ("1.1", "1.2") and (identity_spec or {}).get("enabled"):
        import identity_sim as _isim
        _ok, _e, inorm = _isim.validate_identity_spec(identity_spec)
        if _ok:
            inorm["pool"] = _isim.pool_meta(inorm["count"], inorm["seed"])
            normalized["identity_sim"] = inorm
    normalized["scenario_sha256"] = sha256_text(json.dumps(normalized, sort_keys=True))
    return normalized


def visual_to_yaml(visual):
    """Convert Visual Mode graph (node tree) -> scenario YAML text.
    Same validation rules apply afterwards; the converter never bypasses policy.
    visual: {name, description, duration_seconds, virtual_users, max_rps,
             ramp: [{after_seconds, virtual_users}], think_time_ms:{min,max},
             routes: [{path, method?, weight, timeout_ms?}]}
    """
    routes = visual.get("routes") or []
    idsim_on = bool((visual.get("identity_sim") or {}).get("enabled"))
    lines = [f'schema_version: "{"1.1" if idsim_on else "1.0"}"',
             f'name: "{str(visual.get("name") or "visual-scenario")[:80]}"',
             'target_ref: "galardo-lab-target"']
    if visual.get("description"):
        lines.append(f'description: "{str(visual["description"])[:120]}"')
    lines.append("profile:")
    lines.append(f'  duration_seconds: {int(visual.get("duration_seconds") or 30)}')
    lines.append(f'  virtual_users: {int(visual.get("virtual_users") or 5)}')
    lines.append(f'  max_rps: {int(visual.get("max_rps") or 20)}')
    ramp = visual.get("ramp") or []
    if ramp:
        lines.append("  ramp:")
        for r in ramp:
            lines.append(f'    - after_seconds: {int(r.get("after_seconds") or 0)}')
            lines.append(f'      virtual_users: {int(r.get("virtual_users") or 1)}')
    lines.append("requests:")
    if not routes:
        routes = [{"path": "/healthz", "weight": 100}]
    for r in routes:
        method = (r.get("method") or "GET").upper()
        lines.append(f'  - name: "{str(r.get("name") or r.get("path") or "req")[:40]}"')
        lines.append(f'    method: "{method}"')
        lines.append(f'    path: "{r.get("path") or "/"}"')
        lines.append(f'    weight: {int(r.get("weight") or 50)}')
        lines.append(f'    timeout_ms: {int(r.get("timeout_ms") or 2000)}')
    tt = visual.get("think_time_ms") or {}
    lines.append("think_time_ms:")
    lines.append(f'  min: {int(tt.get("min") if tt.get("min") is not None else 100)}')
    lines.append(f'  max: {int(tt.get("max") if tt.get("max") is not None else 300)}')
    idsim = visual.get("identity_sim") or {}
    if idsim.get("enabled"):
        lines.append("identity_sim:")
        lines.append('  enabled: true')
        lines.append(f'  count: {int(idsim.get("count") or 1000)}')
        lines.append(f'  churn: "{idsim.get("churn") or "per-iteration"}"')
        lines.append(f'  path: "{idsim.get("path") or "edge"}"')
        lines.append(f'  seed: "{idsim.get("seed") or "default-seed"}"')
    return "\n".join(lines) + "\n"


def save_scenario_version(db, scenario_id, normalized, created_by):
    """Create an immutable ScenarioVersion. Hash from canonical JSON, not raw YAML."""
    versions = db.list("scenario_versions", lambda v: v.get("scenario_id") == scenario_id)
    version_no = max([v.get("version_no", 0) for v in versions] or [0]) + 1
    doc = {
        "id": f"scv-{scenario_id}-{version_no}",
        "scenario_id": scenario_id,
        "version_no": version_no,
        "schema_version": normalized.get("schema_version", "1.0"),
        "yaml_text": None,  # raw YAML not stored in version; canonical form is the truth
        "normalized_json": normalized,
        "content_sha256": normalized["scenario_sha256"],
        "created_by": created_by,
        "created_at": None,
        "review_status": "VALIDATED",
    }
    import db as dbm
    dbm.insert("scenario_versions", doc, actor=created_by,
               action="scenario_version.created", resource_type="scenario_version",
               reason=f"version {version_no} hash={normalized['scenario_sha256'][:16]}")
    db.update("scenarios", scenario_id, lambda s: s.update({
        "current_version_id": doc["id"], "current_version_no": version_no,
        "current_hash": normalized["scenario_sha256"]}),
        actor=created_by, action="scenario.version_pinned", resource_type="scenario")
    return doc
