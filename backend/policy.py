"""GALARDO - Safety policy hierarchy and intersection (Technical Design §9).

Hierarchy: GLOBAL -> ORG/ENGAGEMENT -> TEST PLAN -> SCENARIO.
Effective policy = strictest combination:
- numeric caps -> minimum
- allowed hosts/paths -> intersection
- any unknown/missing safety value -> reject (fail closed)
"""
from util import parse_origin


def _min(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _intersect_sets(a, b):
    if a is None:
        return b
    if b is None:
        return a
    out = set(a) & set(b)
    return sorted(out)


def effective_policy(policy_layers):
    """policy_layers: list of policy dicts ordered global -> org -> plan -> scenario.
    Each: {max_rps, max_vus, max_duration_sec, max_concurrency, allowed_hosts, allowed_paths, name}
    Returns (effective, warnings)."""
    warnings = []
    eff = {
        "max_rps": None,
        "max_vus": None,
        "max_duration_sec": None,
        "max_concurrency": None,
        "allowed_hosts": None,
        "allowed_paths": None,
    }
    for layer in policy_layers:
        if not layer:
            continue
        for k in ("max_rps", "max_vus", "max_duration_sec", "max_concurrency"):
            v = layer.get(k)
            if v is not None:
                eff[k] = _min(eff[k], v)
        for k in ("allowed_hosts", "allowed_paths"):
            v = layer.get(k)
            if v is not None:
                eff[k] = _intersect_sets(eff[k], v)

    # A missing cap at every layer means policy is undefined -> fail closed at validation time.
    return eff, warnings


def validate_against_policy(requested, eff, target):
    """Validate requested scenario profile against effective policy.
    Returns list of field-level errors (empty = OK)."""
    errors = []

    def cap(field, label):
        rv = requested.get(field)
        pv = eff.get(field)
        if pv is None:
            errors.append({"field": field, "code": "policy_undefined",
                           "message": f"No effective policy cap defined for {label}; refusing to run (fail-closed)"})
        elif rv is not None and rv > pv:
            errors.append({"field": field, "code": "over_limit",
                           "message": f"Requested {label}={rv} exceeds effective policy cap {pv}"})

    cap("max_rps", "max_rps")
    cap("max_vus", "virtual_users")
    cap("max_duration_sec", "duration_seconds")
    cap("max_concurrency", "concurrency")

    # Host/paths scope intersection enforcement
    origin = parse_origin(target.get("canonical_origin", ""))
    if origin:
        host = origin[1]
        allowed_hosts = eff.get("allowed_hosts")
        if allowed_hosts is not None and host not in allowed_hosts:
            errors.append({"field": "target_ref", "code": "host_not_allowed",
                           "message": f"Target host '{host}' not in effective allowed_hosts {allowed_hosts}"})

    req_paths = requested.get("paths") or []
    allowed_paths = eff.get("allowed_paths")
    if allowed_paths is not None:
        for p in req_paths:
            if p not in allowed_paths:
                errors.append({"field": "paths", "code": "path_not_allowed",
                               "message": f"Request path '{p}' not in effective allowed_paths {allowed_paths}"})
    return errors


def load_policy_layers(db, engagement_id=None, plan_policy_id=None):
    """Load the ACTIVE policy chain (global -> engagement -> plan).
    When multiple global versions exist, only the newest non-superseded one
    applies: superseded versions are kept for audit/immutable evidence but
    must NOT intersect caps (that would freeze the old allowlist forever)."""
    layers = []
    order = {"GLOBAL": 0, "ORG": 1, "ENGAGEMENT": 2, "TEST_PLAN": 3}
    pols = db.list("safety_policies", lambda p: p.get("status") in ("APPROVED", "ACTIVE"))
    pols = sorted(pols, key=lambda p: order.get(p.get("scope_type"), 9))
    for p in pols:
        if p.get("scope_type") == "ENGAGEMENT" and engagement_id and p.get("scope_id") != engagement_id:
            continue
        if p.get("scope_type") == "TEST_PLAN" and plan_policy_id and p.get("id") != plan_policy_id:
            continue
        layers.append(p)
    return layers


def resolve_scenario_layers(db, scenario, engagement_id=None):
    """Effective layers for a scenario: global/org + scenario request itself."""
    layers = load_policy_layers(db, engagement_id=engagement_id)
    prof = scenario.get("profile") or {}
    origin = None
    tgt = db.get("targets", scenario.get("target_id")) if scenario.get("target_id") else None
    if tgt:
        origin = tgt.get("canonical_origin")
    layers.append({
        "name": f"scenario:{scenario.get('name')}",
        "max_rps": prof.get("max_rps"),
        "max_vus": prof.get("virtual_users"),
        "max_duration_sec": prof.get("duration_seconds"),
        "max_concurrency": prof.get("max_concurrency"),
        "allowed_hosts": [origin.split("://")[1].split(":")[0]] if origin else None,
        "allowed_paths": [r.get("path") for r in scenario.get("requests", []) if r.get("path")],
    })
    return layers
