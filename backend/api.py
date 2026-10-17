"""GALARDO - REST API + dashboard static server (stdlib only, ThreadingHTTPServer).

Base path /api/v1 per Technical Design §12. HTTP semantics: 400 malformed,
401 unauthenticated (dev token check), 403 scope, 404 missing, 409 conflict,
422 semantic validation, 429 quota. Audit event on every mutation.
"""
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

import db
import rbac
import mfa
import alerts
import orchestrator
import evidence as evidence_mod
import ownership_ladder as _ladder
from policy import effective_policy, load_policy_layers, resolve_scenario_layers, validate_against_policy
from scenario import parse_scenario_yaml, save_scenario_version, ScenarioError
from util import now_iso, gen_id, sha256_text

try:
    import envload
    envload.load()
except Exception:
    pass


BASE = os.path.dirname(os.path.abspath(__file__))
DASH_DIR = os.path.normpath(os.path.join(BASE, "..", "dashboard"))
DEV_TOKEN = os.environ.get("GALARDO_DEV_TOKEN", "dev-token")  # MVP lab: seeded dev users only
MAX_BODY = 262144

# Goal 3: route overrides live in THIS process (the intercept shim is a local
# server owned by the API). Registry is process-local by design.
OVERRIDES = {}
OVERRIDES_LOCK = threading.Lock()

SOURCES_LOCK = threading.Lock()   # item 9: registry kapabilitas sumber
MIME = {".html": "text/html", ".js": "application/javascript", ".css": "text/css",
        ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png"}

_LADDER_SHORT = {"well_known_file": "file", "http_echo": "echo",
                 "operator_attestation": "attest"}


def seed_lab():
    """Lab-only seed: organization, engagement, target, global+scenario policies,
    health-smoke scenario + immutable version, approved test plan."""
    if db.get("organizations", "org-lab"):
        return {"seeded": False, "note": "already seeded"}

    import time as _t
    now = _t.time()
    from datetime import datetime, timezone
    vf = datetime.fromtimestamp(now - 3600, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    vu = datetime.fromtimestamp(now + 365 * 86400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    import fleet
    fleet.register_all()

    db.insert("organizations", {"id": "org-lab", "name": "Galardo Lab", "status": "ACTIVE",
                                "created_at": now_iso()}, action="org.seeded")
    db.insert("users", {"id": "usr-operator", "org_id": "org-lab", "email": "operator@lab.local",
                        "role": "TEST_OPERATOR", "status": "ACTIVE"}, action="user.seeded")
    eng = {"id": "eng-lab", "org_id": "org-lab", "name": "Lab Resilience Baseline",
           "purpose": "MVP validation of bounded load + safety pipeline",
           "start_at": vf, "end_at": vu, "emergency_contact": "oncall@lab.local",
           "status": "APPROVED", "created_at": now_iso()}
    db.insert("engagements", eng, action="engagement.seeded")

    target_origin = os.environ.get("GALARDO_TARGET_ORIGIN", "http://127.0.0.1:8088")
    target_host = _host_of(target_origin) or "127.0.0.1"
    target = {"id": "tgt-lab", "org_id": "org-lab", "engagement_id": "eng-lab",
              "name": "galardo-lab-target", "environment": "LAB",
              "canonical_origin": target_origin,
              "allowed_hosts": [target_host],
              "allowed_paths": ["/", "/healthz", "/api/slow", "/api/error", "/api/heavy"],
              "probe_contract": {"url": target_origin + "/healthz", "expected_status": 200,
                                 "interval_sec": 1, "timeout_sec": 0.8, "failure_threshold": 3},
              "valid_from": vf, "valid_until": vu, "status": "VERIFIED",
              "created_at": now_iso()}
    db.insert("targets", target, actor="seed", action="target.seeded", resource_type="target")

    pol_global = {"id": "pol-global-v1", "scope_type": "GLOBAL", "scope_id": "org-lab",
                  "version": 1, "name": "Global lab caps",
                  "max_rps": 2000, "max_vus": 1000, "max_duration_sec": 600,
                  "max_concurrency": 2000, "max_error_pct": 30.0, "max_p95_ms": 8000,
                  "allowed_hosts": ["127.0.0.1"],
                  "allowed_paths": ["/", "/healthz", "/api/slow", "/api/error", "/api/heavy"],
                  "status": "APPROVED", "created_at": now_iso(),
                  "policy_sha256": None}
    pol_global["policy_sha256"] = sha256_text(json.dumps(pol_global, sort_keys=True))
    db.insert("safety_policies", pol_global, actor="seed", action="policy.seeded",
              resource_type="safety_policy")

    scenario = {"id": "scn-health-smoke", "org_id": "org-lab", "name": "health-smoke",
                "description": "Low-volume smoke against lab target /healthz",
                "target_id": "tgt-lab", "status": "ACTIVE", "created_at": now_iso()}
    db.insert("scenarios", scenario, action="scenario.seeded", resource_type="scenario")

    yaml_text = """schema_version: "1.2"
name: "health-smoke"
target_ref: "galardo-lab-target"
description: "Low volume smoke test - ACTIVE MODE: GET probe plus POST with body and assertions"
profile:
  duration_seconds: 20
  virtual_users: 2
  max_rps: 4
  ramp:
    - after_seconds: 0
      virtual_users: 1
    - after_seconds: 5
      virtual_users: 2
requests:
  - name: "health"
    method: "GET"
    path: "/healthz"
    weight: 70
    timeout_ms: 1500
    assertions:
      - type: "status_in"
        values: [200]
  - name: "submit"
    method: "POST"
    path: "/"
    weight: 30
    timeout_ms: 1500
    body: "galardo-active-probe"
    body_encoding: "identity"
    assertions:
      - type: "json_contains"
        path: "body"
        value: "galardo-active-probe"
      - type: "soft_body_contains"
        value: "this-string-is-absent-xyz"
think_time_ms:
  min: 100
  max: 250
"""
    targets_by_name = {target["name"]: target}
    norm = parse_scenario_yaml(yaml_text, targets_by_name)
    scv = save_scenario_version(db, scenario["id"], norm, "seed")
    db.update("scenario_versions", scv["id"], lambda v: v.update({"review_status": "APPROVED"}),
              actor="seed", action="scenario_version.approved")

    plan = {"id": "plan-lab-smoke", "engagement_id": "eng-lab", "target_id": "tgt-lab",
            "scenario_id": "scn-health-smoke",
            "scenario_version_id": scv["id"], "policy_version_id": "pol-global-v1",
            "name": "Lab smoke plan", "scheduled_start": vf,
            "approved_by": "seed", "approved_at": now_iso(),
            "status": "APPROVED", "created_at": now_iso()}
    db.insert("test_plans", plan, actor="seed", action="test_plan.seeded", resource_type="test_plan")
    return {"seeded": True, "plan_id": plan["id"], "scenario_version": scv["id"]}


class Handler(BaseHTTPRequestHandler):
    server_version = "GalardoAPI/1.0"

    def log_message(self, fmt, *args):
        pass  # quiet; structured logs handled per-event

    # ---- helpers -------------------------------------------------------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Idempotency-Key")

    def _json(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _auth(self):
        # D14: header ABSENT (lab anonymous) vs header PRESENT but EMPTY (reject).
        raw = self.headers.get("Authorization")
        if raw is None:
            if os.environ.get("GALARDO_REQUIRE_AUTH"):
                return None
            return "usr-operator"  # MVP lab: seeded dev user; production uses SSO/MFA
        tok = raw.strip()
        if not tok:
            return None            # D14: empty header must NOT authenticate
        if tok == f"Bearer {DEV_TOKEN}" or tok == DEV_TOKEN:
            return "usr-operator"
        return None

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("body too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw or b"{}")

    def _route(self):
        p = urlparse(self.path)
        return p.path.rstrip("/") or "/", parse_qs(p.query)

    # ---- tangga verifikasi kepemilikan (Fase A) ------------------------
    def _ladder_handle(self, target_id, method, body, user):
        # Fail-closed: promosi VERIFIED hanya kalau gate lulus pada min_level
        # yang dipilih eksplisit. Attestasi TIDAK pernah diam-diam dianggap bukti.
        tgt = db.get("targets", target_id)
        if not tgt:
            return self._json(404, {"error": "not found"})
        domain = _host_of(tgt.get("canonical_origin") or "")
        if not domain or "." not in domain:
            return self._json(422, {"error": {"field": "canonical_origin",
                                              "message": "cannot derive a domain"}})
        min_level = body.get("min_level") or method
        if min_level not in _ladder.LEVELS:
            return self._json(422, {"error": {"field": "min_level",
                                              "message": "must be one of %s" % list(_ladder.LEVELS)}})
        base_url = (body.get("base_url") or ("https://" + domain)).rstrip("/")
        store = dict(tgt.get("ownership_ladder") or {})

        # rung 4: tidak ada yang perlu dipasang -> verifikasi langsung
        if method == "operator_attestation" and not body.get("reset"):
            proof = _ladder.attest(domain, user,
                                   ttl_seconds=int(body.get("ttl_seconds") or _ladder.DEFAULT_ATTEST_TTL),
                                   note=body.get("note") or "")
            proof.min_level = min_level
            ok, why = _ladder.OwnershipLadder(min_level=min_level).gate(proof)
            db.update("targets", target_id, lambda t: t.update({
                "ownership": method if ok else "operator_attestation_declined",
                "ownership_level": proof.rank, "ownership_min_level": min_level,
                "ownership_proof": proof.to_dict() if ok else None,
                "proof_expires_at": proof.expires_at,
                "status": "VERIFIED" if ok else "UNVERIFIED"}),
                actor=user, action="target.ladder_attest", resource_type="target",
                reason="min_level=%s ok=%s why=%s" % (min_level, ok, why))
            if not ok:
                return self._json(422, {"verified": False, "target_id": target_id,
                                        "method": method, "min_level": min_level,
                                        "reason": why, "evidence": proof.evidence})
            return self._json(200, {"verified": True, "target_id": target_id, "method": method,
                                    "level": proof.rank, "min_level": min_level,
                                    "is_proof": proof.is_proof, "expires_at": proof.expires_at,
                                    "fingerprint": proof.fingerprint(), "reason": why,
                                    "proof": proof.to_dict()})

        rec = store.get(method)
        if body.get("reset") or not rec:
            if method == "http_echo":
                ch = _ladder.EchoChallenge(domain, user, base_url=base_url)
            else:
                ch = _ladder.WellKnownChallenge(domain, user, base_url=base_url)
            store[method] = {"token": ch.token, "base_url": base_url, "min_level": min_level,
                             "issued_at": now_iso(), "attempts": 0}
            db.update("targets", target_id, lambda t: t.update({
                "ownership_ladder": store, "ownership": "%s_pending" % method,
                "ownership_min_level": min_level, "status": "UNVERIFIED"}),
                actor=user, action="target.ladder_challenge_issued", resource_type="target",
                reason="method=%s min_level=%s base_url=%s" % (method, min_level, base_url))
            return self._json(201, {
                "target_id": target_id, "method": method, "min_level": min_level,
                "domain": domain, "token": ch.token,
                "instructions": list(ch.instructions()),
                "next": "pasang token lalu POST ulang ke /targets/%s/verify/%s"
                        % (target_id, _LADDER_SHORT[method])})

        rec = dict(rec)
        rec["attempts"] = int(rec.get("attempts") or 0) + 1
        store[method] = rec
        if method == "http_echo":
            ch = _ladder.EchoChallenge(domain, user, token=rec["token"], base_url=rec["base_url"])
            proof = _ladder.verify_http_echo(ch)
        else:
            ch = _ladder.WellKnownChallenge(domain, user, token=rec["token"], base_url=rec["base_url"])
            proof = _ladder.verify_well_known(ch)
        proof.min_level = min_level
        ok, why = _ladder.OwnershipLadder(min_level=min_level).gate(proof)
        db.update("targets", target_id, lambda t: t.update({
            "ownership_ladder": store,
            "ownership": method if ok else "%s_pending" % method,
            "ownership_level": proof.rank, "ownership_min_level": min_level,
            "ownership_proof": proof.to_dict() if ok else None,
            "proof_expires_at": proof.expires_at,
            "status": "VERIFIED" if ok else "UNVERIFIED"}),
            actor=user, action="target.ladder_verify", resource_type="target",
            reason="method=%s min_level=%s ok=%s why=%s" % (method, min_level, ok, why))
        if not ok:
            return self._json(422, {"verified": False, "target_id": target_id, "method": method,
                                    "min_level": min_level, "reason": why,
                                    "evidence": proof.evidence, "attempts": rec["attempts"]})
        return self._json(200, {"verified": True, "target_id": target_id, "method": method,
                                "level": proof.rank, "min_level": min_level,
                                "is_proof": proof.is_proof, "expires_at": proof.expires_at,
                                "fingerprint": proof.fingerprint(), "reason": why,
                                "proof": proof.to_dict()})


    # ---- static --------------------------------------------------------
    def _static(self, path):
        # D11: normalise separators, drop query/fragment, block traversal.
        path = path.split("?")[0].split("#")[0].replace("\\", "/")
        parts = [seg for seg in path.split("/") if seg not in ("", ".")]
        root = os.path.normpath(DASH_DIR)
        fp = os.path.normpath(os.path.join(root, *parts)) if parts else os.path.join(root, "index.html")
        if fp != root and not fp.startswith(root + os.sep):
            fp = os.path.join(root, "index.html")
        if not fp.startswith(DASH_DIR) or not os.path.isfile(fp):
            self._json(404, {"error": "not found"})
            return
        ext = os.path.splitext(fp)[1]
        data = open(fp, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        try:
            self._dispatch("GET")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        try:
            self._dispatch("POST")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_DELETE(self):
        try:
            self._dispatch("DELETE")
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- router --------------------------------------------------------
    def _dispatch(self, method):
        path, q = self._route()
        if not path.startswith("/api"):
            if method == "GET":
                return self._static(path)
            return self._json(404, {"error": "not found"})

        api_path = path[len("/api/v1"):] or "/"

        # --- RBAC (item 8 / STEP-64) ---
        if api_path == "/me" and method == "GET":
            uid = self._auth()
            return self._json(200, {"actor": uid, "user": rbac.public(rbac.user_of(uid))})

        if api_path == "/me/mfa/enroll" and method == "POST":
            uid = self._auth()
            try:
                secret = mfa.gen_secret()
                def _en(d, secret=secret, uid=uid):
                    d["id"] = d.get("id") or uid
                    d["mfa_secret"] = secret
                    d["mfa_enabled"] = False
                    d["mfa_last_step"] = None
                    return d
                if db.get("users", uid):
                    u = db.update("users", uid, _en, actor=uid, action="mfa.enrolled")
                else:
                    u = db.insert("users", _en({"id": uid}), actor=uid, action="mfa.enrolled")
                return self._json(200, {"secret": secret,
                                        "otpauth": mfa.provisioning_uri(secret, (u or {}).get("email") or uid),
                                        "mfa_enabled": False})
            except Exception as exc:
                return self._json(500, {"error": type(exc).__name__ + ": " + str(exc)})

        if api_path == "/me/mfa/verify" and method == "POST":
            uid = self._auth()
            try:
                u = db.get("users", uid)
                if not u or not u.get("mfa_secret"):
                    return self._json(422, {"error": "belum enroll"})
                body = self._body() if hasattr(self, "_body") else {}
                last = u.get("mfa_last_step") if u.get("mfa_enabled") else None
                ok, step, drift = mfa.verify(u.get("mfa_secret"), body.get("code"), last_step=last)
                if not ok:
                    return self._json(422, {"error": "kode salah", "step": step, "drift": drift})
                def _vf(d, step=step):
                    d["mfa_enabled"] = True
                    d["mfa_last_step"] = step
                    return d
                db.update("users", uid, _vf, actor=uid, action="mfa.verified")
                return self._json(200, {"mfa_enabled": True, "step": step, "drift": drift})
            except Exception as exc:
                return self._json(500, {"error": type(exc).__name__ + ": " + str(exc)})

        if api_path == "/me/mfa/disable" and method == "POST":
            uid = self._auth()
            try:
                if not db.get("users", uid):
                    return self._json(404, {"error": "user tidak ada"})
                def _of(d):
                    d["mfa_enabled"] = False
                    d["mfa_last_step"] = None
                    d.pop("mfa_secret", None)
                    return d
                db.update("users", uid, _of, actor=uid, action="mfa.disabled")
                return self._json(200, {"mfa_enabled": False})
            except Exception as exc:
                return self._json(500, {"error": type(exc).__name__ + ": " + str(exc)})

        if api_path == "/alerts" and method == "GET":
            uid = self._auth()
            try:
                ok, why = rbac.ensure(rbac.user_of(uid), "VIEWER")
                if not ok:
                    return self._json(403, {"error": why})
                return self._json(200, alerts.list_rules())
            except Exception as exc:
                return self._json(500, {"error": type(exc).__name__ + ": " + str(exc)})

        if api_path == "/alerts" and method == "POST":
            uid = self._auth()
            try:
                ok, why = rbac.ensure(rbac.user_of(uid), "TEST_OPERATOR")
                if not ok:
                    return self._json(403, {"error": why})
                body = self._body() if hasattr(self, "_body") else {}
                rule, err = alerts.add(body.get("event") or "", body.get("hook_id") or "",
                                       field=body.get("field"), value=body.get("value"),
                                       note=body.get("note"), actor=uid)
                if err:
                    return self._json(422, {"error": err, "events": list(alerts._event_types())})
                return self._json(201, rule)
            except Exception as exc:
                return self._json(500, {"error": type(exc).__name__ + ": " + str(exc)})

        _ma = _match(api_path, "/alerts/*/remove")
        if _ma and method == "POST":
            uid = self._auth()
            try:
                ok, why = rbac.ensure(rbac.user_of(uid), "TEST_OPERATOR")
                if not ok:
                    return self._json(403, {"error": why})
                if not alerts.remove(_g1(_ma)):
                    return self._json(404, {"error": "aturan tidak ada"})
                return self._json(200, {"removed": _g1(_ma)})
            except Exception as exc:
                return self._json(500, {"error": type(exc).__name__ + ": " + str(exc)})

        if api_path == "/users" and method == "GET":
            uid = self._auth()
            ok, why = rbac.ensure(rbac.user_of(uid), "VIEWER")
            if not ok:
                return self._json(403, {"error": why})
            return self._json(200, [rbac.public(u) for u in db.list("users")])

        if api_path == "/users" and method == "POST":
            uid = self._auth()
            try:
                ok, why = rbac.ensure(rbac.user_of(uid), "TEST_OPERATOR")
                if not ok:
                    return self._json(403, {"error": why})
                body = self._body() if hasattr(self, "_body") else {}
                role = (body.get("role") or "VIEWER").upper()
                if role not in rbac.ROLE_RANK:
                    return self._json(422, {"error": "peran tak dikenal", "roles": list(rbac.ROLES)})
                email = (body.get("email") or "").strip()
                if not email:
                    return self._json(422, {"error": "email wajib"})
                slug = re.sub(r"[^a-z0-9]+", "-", email.split("@")[0].lower()).strip("-")[:24] or "user"
                _id = "usr-" + slug
                if db.get("users", _id):
                    _id = _id + "-" + str(len(db.list("users")))
                _doc = {"id": _id, "email": email, "role": role, "status": "ACTIVE",
                        "org_id": body.get("org_id")}
                u = db.insert("users", _doc, actor=uid, action="user.created")
                return self._json(201, rbac.public(u if isinstance(u, dict) else (db.get("users", _id) or _doc)))
            except Exception as exc:
                return self._json(500, {"error": type(exc).__name__ + ": " + str(exc)})

        _m = _match(api_path, "/users/*/role")
        if _m and method == "POST":
            uid = self._auth()
            ok, why = rbac.ensure(rbac.user_of(uid), "TEST_OPERATOR")
            if not ok:
                return self._json(403, {"error": why})
            if not db.get("users", _g1(_m)):
                return self._json(404, {"error": "user tidak ada"})
            role = ((self._body() if hasattr(self, "_body") else {}).get("role") or "").upper()
            if role not in rbac.ROLE_RANK:
                return self._json(422, {"error": "peran tak dikenal", "roles": list(rbac.ROLES)})
            try:
                u = db.update("users", _g1(_m), lambda d: d.update({"role": role}),
                              actor=uid, action="user.role_changed")
            except Exception as exc:
                return self._json(500, {"error": type(exc).__name__ + ": " + str(exc)})
            return self._json(200, rbac.public(u if isinstance(u, dict) else db.get("users", _g1(_m))))

        if api_path == "/health" and method == "GET":
            return self._json(200, {"status": "ok", "service": "galardo-api", "version": "1.0",
                                    "time": now_iso(),
                                    "local_dev_override": os.environ.get("GALARDO_LOCAL_DEV") == "1"})

        user = self._auth()
        if user is None:
            return self._json(401, {"error": "unauthenticated"})

        try:
            if api_path == "/seed" and method == "POST":
                return self._json(200, seed_lab())

            # ---- policies (read; mutations via change process only) ----
            if api_path == "/policies" and method == "GET":
                return self._json(200, db.list("safety_policies"))
            if api_path == "/policies" and method == "POST":
                # Create new policy VERSION (audited). Supersedes the previous
                # version of the same scope. Runs INSIDE the API process so the
                # state cache stays coherent (multi-process file writes race).
                b = self._body()
                scope_type = b.get("scope_type", "GLOBAL")
                prev = [p for p in db.list("safety_policies")
                        if p.get("scope_type") == scope_type and p.get("status") in ("APPROVED", "ACTIVE")]
                prev.sort(key=lambda p: p.get("version", 0))
                version = (prev[-1].get("version", 0) + 1) if prev else 1
                pol = {"id": f"pol-{scope_type.lower()}-v{version}",
                       "scope_type": scope_type, "scope_id": b.get("scope_id", "org-lab"),
                       "version": version, "name": b.get("name", f"{scope_type} caps v{version}"),
                       "max_rps": b.get("max_rps"), "max_vus": b.get("max_vus"),
                       "max_duration_sec": b.get("max_duration_sec"),
                       "max_concurrency": b.get("max_concurrency"),
                       "max_error_pct": b.get("max_error_pct"), "max_p95_ms": b.get("max_p95_ms"),
                       "allowed_hosts": b.get("allowed_hosts"),
                       "allowed_paths": b.get("allowed_paths"),
                       "status": "APPROVED", "created_at": now_iso(),
                       "policy_sha256": None, "supersedes": prev[-1]["id"] if prev else None,
                       "created_by": user}
                pol["policy_sha256"] = sha256_text(json.dumps({k: v for k, v in pol.items() if k != "policy_sha256"}, sort_keys=True))
                db.insert("safety_policies", pol, actor=user, action="policy.version_created",
                          resource_type="safety_policy",
                          reason=f"v{version} via API; supersedes {prev[-1]['id'] if prev else 'none'}")
                for p in prev:
                    db.update("safety_policies", p["id"], lambda x: x.update({"status": "SUPERSEDED"}),
                              actor=user, action="policy.superseded", resource_type="safety_policy",
                              reason=f"replaced by {pol['id']}")
                return self._json(201, pol)

            # ---- overview ----
            if api_path == "/overview" and method == "GET":
                return self._json(200, overview())

            # ---- engagements ----
            if api_path == "/engagements" and method == "GET":
                return self._json(200, db.list("engagements"))
            if api_path == "/engagements" and method == "POST":
                b = self._body()
                if not b.get("name"):
                    return self._json(422, {"error": {"field": "name", "message": "required"}})
                eng = {"id": gen_id("eng"), "org_id": "org-lab", "name": b["name"],
                       "purpose": b.get("purpose", ""), "start_at": b.get("start_at"),
                       "end_at": b.get("end_at"),
                       "emergency_contact": b.get("emergency_contact", ""),
                       "status": "DRAFT", "created_at": now_iso()}
                db.insert("engagements", eng, actor=user, action="engagement.created",
                          resource_type="engagement")
                return self._json(201, eng)
            m = _match(api_path, "/engagements/*/approve")
            if m and method == "POST":
                eng = db.get("engagements", m[0])
                if not eng:
                    return self._json(404, {"error": "not found"})
                if eng["status"] == "APPROVED":
                    return self._json(409, {"error": "already APPROVED"})
                db.update("engagements", m[0], lambda e: e.update({"status": "APPROVED"}),
                          actor=user, action="engagement.approved", resource_type="engagement")
                return self._json(200, db.get("engagements", m[0]))

            # ---- targets ----
            if api_path == "/targets" and method == "GET":
                return self._json(200, db.list("targets"))
            # LOCAL DEV OVERRIDE: saat env GALARDO_LOCAL_DEV=1, target baru langsung
            # VERIFIED (operator attestation ter-audit) tanpa verifikasi DNS/file.
            # Safety pipeline (policy, preflight, probe, abort) TETAP aktif penuh.
            # Default: OFF. Hanya relevan di local development (deployment produksi
            # wajib env ini tidak diset / server fisik).
            LOCAL_DEV = os.environ.get("GALARDO_LOCAL_DEV") == "1"
            if api_path == "/targets" and method == "POST":
                b = self._body()
                eng = db.get("engagements", b.get("engagement_id", ""))
                if not eng:
                    return self._json(422, {"error": {"field": "engagement_id", "message": "not found"}})
                origin = b.get("canonical_origin", "")
                if not origin.startswith(("http://", "https://")):
                    return self._json(422, {"error": {"field": "canonical_origin",
                                                      "message": "must be http(s) origin"}})
                if LOCAL_DEV:
                    status = "VERIFIED"
                    valid_until = b.get("valid_until") or (datetime.now(timezone.utc)
                                    + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    status = "UNVERIFIED"
                    valid_until = b.get("valid_until")
                tgt = {"id": gen_id("tgt"), "org_id": "org-lab", "engagement_id": eng["id"],
                       "name": b.get("name", origin), "environment": b.get("environment", "LAB"),
                       "canonical_origin": origin,
                       "allowed_hosts": b.get("allowed_hosts") or [_host_of(origin)],
                       "allowed_paths": b.get("allowed_paths") or ["/"],
                       "probe_contract": b.get("probe_contract") or {
                           "url": origin + "/healthz", "expected_status": 200,
                           "interval_sec": 2, "timeout_sec": 1, "failure_threshold": 3},
                       "valid_from": b.get("valid_from") or now_iso(),
                       "valid_until": valid_until,
                       "ownership": ("operator_attestation_local_dev" if LOCAL_DEV else "pending_verification"),
                       "status": status, "created_at": now_iso()}
                db.insert("targets", tgt, actor=user, action="target.created", resource_type="target",
                          reason=("LOCAL DEV OVERRIDE: operator attestation - auto-VERIFIED, "
                                  "window 1 day, no DNS/file verification" if LOCAL_DEV else ""))
                if LOCAL_DEV:
                    db.audit_event(user, "target.local_dev_auto_verified", "target", tgt["id"],
                                   reason=f"GALARDO_LOCAL_DEV=1; origin={origin}; "
                                          f"attestation by {user}; window 24h")
                return self._json(201, tgt)
            m = _match(api_path, "/targets/*/probe-contract")
            if m and method == "POST":
                b = self._body()
                tgt = db.get("targets", m[0])
                if not tgt:
                    return self._json(404, {"error": "not found"})
                allowed = {"url", "expected_status", "interval_sec", "timeout_sec", "failure_threshold"}
                patch = {k: v for k, v in b.items() if k in allowed}
                if not patch:
                    return self._json(422, {"error": "no valid probe_contract fields"})
                db.update("targets", m[0], lambda t: t["probe_contract"].update(patch),
                          actor=user, action="target.probe_contract_updated", resource_type="target",
                          reason=json.dumps(patch))
                return self._json(200, db.get("targets", m[0]))
            m = _match(api_path, "/targets/*/challenge")
            if m and method == "POST":
                import ownership as _own
                tgt = db.get("targets", m[0])
                if not tgt:
                    return self._json(404, {"error": "not found"})
                domain = _host_of(tgt.get("canonical_origin") or "")
                if not domain or "." not in domain:
                    return self._json(422, {"error": {"field": "canonical_origin",
                                                      "message": "cannot derive a registrable domain"}})
                ch = _own.Challenge(domain, user)
                db.update("targets", m[0], lambda t: t.update({
                    "ownership": "dns_txt_pending",
                    "ownership_challenge": ch.to_dict(),
                    "status": "UNVERIFIED",
                }), actor=user, action="target.challenge_issued", resource_type="target",
                    reason=f"TXT {ch.record_name} expected (quorum 2 of 3 resolvers)")
                return self._json(201, {
                    "target_id": m[0], "domain": domain,
                    "record_name": ch.record_name, "expected_value": ch.expected_value,
                    "ttl_seconds": ch.ttl_seconds, "instructions": list(ch.instructions()),
                    "next": "publish the TXT record, then POST /targets/%s/verify/dns" % m[0],
                })
            m = _match(api_path, "/targets/*/verify/dns")
            if m and method == "POST":
                import ownership as _own
                tgt = db.get("targets", m[0])
                if not tgt:
                    return self._json(404, {"error": "not found"})
                stored = tgt.get("ownership_challenge")
                if not stored:
                    return self._json(422, {"error": "no challenge issued - POST /targets/*/challenge first"})
                ch = _own.Challenge.from_dict(stored)
                proof = _own.OwnershipVerifier().verify(ch)
                db.update("targets", m[0], lambda t: t.update({
                    "ownership_challenge": ch.to_dict(),
                    "ownership": "dns_txt_quorum" if proof.ok else "dns_txt_pending",
                    "ownership_proof": proof.to_dict() if proof.ok else None,
                    "status": "VERIFIED" if proof.ok else "UNVERIFIED",
                }), actor=user, action="target.verify_dns", resource_type="target",
                    reason=f"quorum ok={proof.ok} label={proof.label} attempts={ch.attempts}")
                if not proof.ok:
                    return self._json(422, {"verified": False, "target_id": m[0],
                                            "record_name": ch.record_name,
                                            "expected_value": ch.expected_value,
                                            "attempts": ch.attempts,
                                            "evidence": proof.evidence})
                return self._json(200, {"verified": True, "target_id": m[0],
                                        "record_name": proof.record, "label": proof.label,
                                        "fingerprint": proof.fingerprint(),
                                        "proof": proof.to_dict()})
            # ---- tangga verifikasi kepemilikan (Fase A) ----
            m = _match(api_path, "/targets/*/verify/file")
            if m and method == "POST":
                return self._ladder_handle(m[0], "well_known_file", self._body(), user)
            m = _match(api_path, "/targets/*/verify/echo")
            if m and method == "POST":
                return self._ladder_handle(m[0], "http_echo", self._body(), user)
            m = _match(api_path, "/targets/*/verify/attest")
            if m and method == "POST":
                return self._ladder_handle(m[0], "operator_attestation", self._body(), user)
            m = _match(api_path, "/targets/*/ownership")
            if m and method == "GET":
                tgt = db.get("targets", m[0])
                if not tgt:
                    return self._json(404, {"error": "not found"})
                store = tgt.get("ownership_ladder") or {}
                return self._json(200, {
                    "target_id": m[0], "status": tgt.get("status"),
                    "ownership": tgt.get("ownership"),
                    "ownership_level": tgt.get("ownership_level"),
                    "ownership_min_level": tgt.get("ownership_min_level"),
                    "proof_expires_at": tgt.get("proof_expires_at"),
                    "proof": tgt.get("ownership_proof"),
                    "rungs": [{"method": k, "rank": _ladder.LEVEL_RANK.get(k),
                               "is_proof": _ladder.LEVEL_IS_PROOF.get(k),
                               "issued_at": v.get("issued_at"), "attempts": v.get("attempts")}
                              for k, v in sorted(store.items())],
                    "available_levels": list(_ladder.LEVELS)})
            m = _match(api_path, "/targets/*/verify")
            if m and method == "POST":
                tgt = db.get("targets", m[0])
                if not tgt:
                    return self._json(404, {"error": "not found"})
                if not tgt.get("valid_until"):
                    return self._json(422, {"error": {"field": "valid_until",
                                                      "message": "ownership document window required before verify"}})
                db.update("targets", m[0], lambda t: t.update({"status": "VERIFIED"}),
                          actor=user, action="target.verified", resource_type="target")
                return self._json(200, db.get("targets", m[0]))

            # ---- scenarios ----
            if api_path == "/scenarios" and method == "GET":
                out = []
                for s in db.list("scenarios"):
                    s2 = dict(s)
                    s2["versions"] = sorted(
                        [v for v in db.list("scenario_versions") if v["scenario_id"] == s["id"]],
                        key=lambda v: v.get("version_no", 0))
                    out.append(s2)
                return self._json(200, out)
            if api_path == "/scenarios/validate" and method == "POST":
                b = self._body()
                targets_by_name = {t["name"]: t for t in db.list("targets")}
                yaml_text = b.get("yaml")
                if not yaml_text and isinstance(b.get("visual"), dict):
                    from scenario import visual_to_yaml
                    yaml_text = visual_to_yaml(b["visual"])
                try:
                    norm = parse_scenario_yaml(yaml_text, targets_by_name)
                except ScenarioError as e:
                    return self._json(422, {"valid": False, "errors": e.errors})
                tgt = db.get("targets", norm["target_id"])
                layers = resolve_scenario_layers(db, norm, engagement_id=tgt.get("engagement_id") if tgt else None)
                eff, _ = effective_policy(layers)
                eff["max_rps"] = min(eff["max_rps"] or norm["profile"]["max_rps"], norm["profile"]["max_rps"])
                eff["max_vus"] = min(eff["max_vus"] or norm["profile"]["virtual_users"], norm["profile"]["virtual_users"])
                eff["max_duration_sec"] = min(eff["max_duration_sec"] or norm["profile"]["duration_seconds"],
                                              norm["profile"]["duration_seconds"])
                policy_errors = validate_against_policy(
                    {"max_rps": norm["profile"]["max_rps"], "max_vus": norm["profile"]["virtual_users"],
                     "max_duration_sec": norm["profile"]["duration_seconds"],
                     "paths": norm["request_paths"]},
                    eff, tgt or {})
                if policy_errors:
                    return self._json(422, {"valid": False, "errors": policy_errors,
                                            "scenario_hash": norm["scenario_sha256"]})
                return self._json(200, {"valid": True, "scenario_hash": norm["scenario_sha256"],
                                        "normalized": norm, "effective_limits": eff, "warnings": []})
            if api_path == "/scenarios/visual-to-yaml" and method == "POST":
                from scenario import visual_to_yaml
                b = self._body()
                try:
                    return self._json(200, {"yaml": visual_to_yaml(b.get("visual") or {})})
                except Exception as e:
                    return self._json(422, {"error": f"visual invalid: {e}"})
            if api_path == "/scenarios" and method == "POST":
                b = self._body()
                targets_by_name = {t["name"]: t for t in db.list("targets")}
                yaml_text = b.get("yaml")
                if not yaml_text and isinstance(b.get("visual"), dict):
                    from scenario import visual_to_yaml
                    yaml_text = visual_to_yaml(b["visual"])
                try:
                    norm = parse_scenario_yaml(yaml_text, targets_by_name)
                except ScenarioError as e:
                    return self._json(422, {"valid": False, "errors": e.errors})
                if b.get("scenario_id"):
                    scn = db.get("scenarios", b["scenario_id"])
                    if not scn:
                        return self._json(404, {"error": "scenario not found"})
                    scv = save_scenario_version(db, scn["id"], norm, user)
                    return self._json(201, scv)
                scn = {"id": gen_id("scn"), "org_id": "org-lab", "name": norm["name"],
                       "description": norm.get("description", ""), "target_id": norm["target_id"],
                       "status": "ACTIVE", "created_at": now_iso()}
                db.insert("scenarios", scn, actor=user, action="scenario.created", resource_type="scenario")
                scv = save_scenario_version(db, scn["id"], norm, user)
                return self._json(201, {"scenario": scn, "version": scv})

            # ---- test plans ----
            if api_path == "/test-plans" and method == "GET":
                return self._json(200, db.list("test_plans"))
            if api_path == "/test-plans" and method == "POST":
                b = self._body()
                plan = {"id": gen_id("plan"), "engagement_id": b.get("engagement_id"),
                        "target_id": b.get("target_id"), "scenario_id": b.get("scenario_id"),
                        "scenario_version_id": b.get("scenario_version_id"),
                        "policy_version_id": b.get("policy_version_id"),
                        "name": b.get("name", ""), "scheduled_start": b.get("scheduled_start"),
                        "remote_dispatch": bool(b.get("remote_dispatch")),
                        "status": "DRAFT", "approved_by": None, "approved_at": None,
                        "created_at": now_iso()}
                for ref, col_ in (("engagement_id", "engagements"), ("target_id", "targets"),
                                  ("scenario_version_id", "scenario_versions"),
                                  ("policy_version_id", "safety_policies")):
                    if not db.get(col_, plan.get(ref) or ""):
                        return self._json(422, {"error": {"field": ref, "message": "reference not found"}})
                db.insert("test_plans", plan, actor=user, action="test_plan.created",
                          resource_type="test_plan")
                return self._json(201, plan)
            m = _match(api_path, "/test-plans/*/approve")
            if m and method == "POST":
                plan = db.get("test_plans", m[0])
                if not plan:
                    return self._json(404, {"error": "not found"})
                scv = db.get("scenario_versions", plan.get("scenario_version_id") or "")
                pol = db.get("safety_policies", plan.get("policy_version_id") or "")
                if not scv or scv.get("review_status") not in ("VALIDATED", "APPROVED"):
                    return self._json(422, {"error": "scenario version not validated"})
                if not pol or pol.get("status") not in ("APPROVED", "ACTIVE", "SUPERSEDED"):
                    return self._json(422, {"error": "policy version not approved"})
                db.update("test_plans", m[0], lambda p: p.update({
                    "status": "APPROVED", "approved_by": user, "approved_at": now_iso()}),
                    actor=user, action="test_plan.approved", resource_type="test_plan")
                return self._json(200, db.get("test_plans", m[0]))

            # ---- workers (fleet) ----
            if api_path == "/workers" and method == "GET":
                ws = db.list("workers")
                ws.sort(key=lambda w: w.get("id", ""))
                return self._json(200, ws)
            if api_path == "/workers" and method == "POST":
                b = self._body()
                wid = (b.get("id") or "").strip()
                if not wid or not wid.replace("-", "").replace("_", "").isalnum():
                    return self._json(422, {"error": {"field": "id", "message": "worker id required (alnum/-_)"}})
                existing = db.get("workers", wid)
                if existing:
                    db.update("workers", wid, lambda w: w.update({
                        "status": w.get("status") if w.get("status") == "RUNNING" else "IDLE",
                        "last_heartbeat_at": now_iso(),
                        "capabilities": b.get("capabilities") or w.get("capabilities"),
                        "expertise": b.get("expertise") or w.get("expertise"),
                        "kind": b.get("kind") or w.get("kind"),
                    }), actor=wid, action="worker.re_registered", resource_type="worker")
                    return self._json(200, db.get("workers", wid))
                doc = {"id": wid, "name": b.get("name") or wid,
                       "expertise": b.get("expertise", "distributed-k6"),
                       "capabilities": b.get("capabilities") or ["GET"],
                       "desc": b.get("desc", "remote k6 worker"),
                       "kind": b.get("kind", "k6-remote"),
                       "version": "1.0", "status": "IDLE",
                       "current_job_id": None, "last_heartbeat_at": now_iso(),
                       "lease_expires_at": None, "created_at": now_iso()}
                db.insert("workers", doc, actor=wid, action="worker.registered",
                          resource_type="worker", reason=f"remote worker expertise={doc['expertise']}")
                return self._json(201, doc)
            m = _match(api_path, "/workers/*/heartbeat")
            if m and method == "POST":
                b = self._body()
                w = db.get("workers", m[0])
                if not w:
                    return self._json(404, {"error": "unknown worker - re-register"})

                def mut(w_):
                    w_["last_heartbeat_at"] = now_iso()
                    if b.get("status"):
                        w_["status"] = b["status"]
                    w_["current_job_id"] = b.get("current_job_id")
                db.update("workers", m[0], mut, audit=False)
                return self._json(200, {"ok": True, "server_time": now_iso()})
            m = _match(api_path, "/workers/*/claim")
            if m and method == "POST":
                wid = m[0]
                w = db.get("workers", wid)
                if not w:
                    return self._json(404, {"error": "unknown worker"})
                if w.get("status") != "IDLE":
                    return self._json(200, {"envelope": None, "reason": f"worker {w.get('status')}"})
                # find a job whose plan requests k6-remote execution (fleet scheduler extension)
                env = _claim_remote_job(wid)
                return self._json(200, {"envelope": env})
            m = _match(api_path, "/workers/*/ack")
            if m and method == "POST":
                b = self._body()
                wid, job_id, state = m[0], b.get("job_id"), b.get("state")
                db.observation(job_id or "?", "worker", "INFO",
                               f"remote worker {wid} ACK: {state}" +
                               (f" ({json.dumps(b.get('result', {}))[:200]})" if b.get("result") else ""),
                               correlation_id=None)
                if state in ("READY",):
                    if db.get("test_jobs", job_id or ""):
                        pass  # state machine already RUNNING at dispatch
                if state in ("STOPPED", "REJECTED"):
                    w = db.get("workers", wid)
                    if w and w.get("status") == "RUNNING":
                        db.update("workers", wid, lambda x: x.update({
                            "status": "IDLE", "current_job_id": None}),
                            actor=wid, action="worker.status", resource_type="worker",
                            reason=f"{state} -> IDLE")
                if state == "STOPPED" and job_id and b.get("result"):
                    res = b["result"] or {}
                    summ = res.get("summary") or {}
                    db.observation(job_id, "worker", "INFO",
                                   f"k6 summary: rps={summ.get('rps')} requests={summ.get('requests')} "
                                   f"p95={summ.get('p95_ms')}ms failed_rate={summ.get('failed_rate')}")
                    # finalize the job (remote path): orchestrator owns the state machine
                    job = db.get("test_jobs", job_id)
                    if job and job.get("status") == "RUNNING":
                        db.update("test_jobs", job_id, lambda j: j.update({
                            "final_metrics": {"aggregate": summ, "engine": res,
                                              "generator": "k6-remote", "worker": wid}}), audit=False)
                        import orchestrator as _o
                        _o._set_state(job_id, "STOPPING", actor="worker",
                                      reason="remote k6 finished; flushing summary")
                        # recovery via independent probe, then COMPLETED/RECOVERY_FAILED
                        _o._begin_recovery(job_id, actor="worker")
                return self._json(200, {"ok": True})

            # ---- identity sim: deterministic pool export ----
            if api_path == "/identity-pool" and method == "GET":
                count = int(q.get("count", ["1000"])[0])
                seed = (q.get("seed", ["default-seed"])[0])[:64]
                import identity_sim as _isim
                if not (1 <= count <= _isim.MAX_POOL):
                    return self._json(422, {"error": f"count must be 1..{_isim.MAX_POOL}"})
                pool = _isim.generate_identities(count, seed)
                buckets = {}
                for ident in pool:
                    buckets[str(_isim.bucket_of(ident["ip"]))] = buckets.get(str(_isim.bucket_of(ident["ip"])), 0) + 1
                return self._json(200, {"count": count, "seed": seed,
                                        "pool_sha256": _isim.pool_meta(count, seed)["pool_sha256"],
                                        "bucket_counts": buckets,
                                        "entropy": _isim.entropy([buckets.get(str(i), 0) for i in range(_isim.BUCKETS)]),
                                        "sample": pool[:5],
                                        "note": "header-level identities only; regenerate deterministically on any worker"})

            # ---- cluster config (remote dispatch opt-in) ----
            if api_path == "/config/remote-dispatch" and method == "GET":
                return self._json(200, db.get("config", "remote_dispatch") or {"enabled": False})
            if api_path == "/config/remote-dispatch" and method == "POST":
                b = self._body()
                doc = {"id": "remote_dispatch", "enabled": bool(b.get("enabled")),
                       "updated_at": now_iso(), "updated_by": user}
                db.insert("config", doc, actor=user, action="config.remote_dispatch",
                          resource_type="config",
                          reason=f"enabled={doc['enabled']} (remote k6 worker claiming)")
                return self._json(200, doc)

            # ---- AI advisory insights ----
            m = _match(api_path, "/test-jobs/*/insights")
            if m and method == "GET":
                import insights
                result = insights.analyze_job(m[0], orchestrator_mod=orchestrator)
                if result is None:
                    return self._json(404, {"error": "job not found"})
                return self._json(200, result)

            # ---- jobs ----
            if api_path == "/test-jobs" and method == "GET":
                return self._json(200, db.list("test_jobs"))
            if api_path == "/test-jobs" and method == "POST":
                b = self._body()
                idem = self.headers.get("Idempotency-Key")
                try:
                    job, created = orchestrator.create_job(b.get("test_plan_id"), user, idem)
                except ValueError as e:
                    return self._json(422, {"error": str(e)})
                return self._json(202 if created else 200, job)
            m = _match(api_path, "/test-jobs/*")
            if m and method == "GET" and len(m) == 1:
                job = db.get("test_jobs", m[0])
                if not job:
                    return self._json(404, {"error": "not found"})
                snap = orchestrator.get_runtime_snapshot(m[0])
                return self._json(200, snap)
            m = _match(api_path, "/test-jobs/*/start")
            if m and method == "POST":
                ok, checks = orchestrator.start_job(m[0], actor=user)
                return self._json(200 if ok else 409, {"started": ok, "preflight": checks})
            m = _match(api_path, "/test-jobs/*/abort")
            if m and method == "POST":
                b = self._body()
                reason = (b.get("reason") or "").strip()
                if not reason:
                    return self._json(422, {"error": {"field": "reason",
                                                      "message": "abort reason is mandatory (audit)"}})
                status, info = orchestrator.abort_job(m[0], reason, actor=user)
                if status is None:
                    return self._json(404, {"error": "not found"})
                return self._json(202, {"job_id": m[0], "status": status, **info})
            m = _match(api_path, "/test-jobs/*/recovery")
            if m and method == "POST":
                status = orchestrator.monitor_recovery(m[0], actor=user)
                if status is None:
                    return self._json(404, {"error": "not found"})
                return self._json(202, {"job_id": m[0], "status": status})
            m = _match(api_path, "/test-jobs/*/reconcile")
            if m and method == "POST":
                # fail-safe reconcile: for jobs stuck in transient states with NO live
                # runtime context (engine never started or process died). Zero-traffic
                # reconcile only; audited. Cannot touch RUNNING jobs with live ctx.
                import orchestrator as _o
                job = db.get("test_jobs", m[0])
                if not job:
                    return self._json(404, {"error": "not found"})
                with _o.JOBS_LOCK:
                    has_live_ctx = m[0] in _o.JOBS
                if has_live_ctx:
                    return self._json(409, {"error": "live runtime context exists - use abort"})
                if job["status"] in ("ABORT_REQUESTED", "ABORTING", "RUNNING", "STOPPING",
                                     "RECOVERY_WAIT", "DISPATCHING", "PENDING", "PREFLIGHT"):
                    # RUNNING/STOPPING only reachable here when runtime ctx is gone
                    # (worker daemon death) - safe to close as ABORTED, zero unknown traffic
                    _o._set_state(m[0], "ABORTING", actor=user,
                                  reason="reconcile: no runtime context (zero-traffic job)")
                    _o._set_state(m[0], "ABORTED", actor=user,
                                  reason="reconcile: zero-traffic job reconciled by operator")
                    return self._json(200, {"job_id": m[0], "status": "ABORTED", "reconciled": True})
                return self._json(409, {"error": f"cannot reconcile state {job['status']}"})
            m = _match(api_path, "/test-jobs/*/live")
            if m and method == "GET":
                snap = orchestrator.get_runtime_snapshot(m[0])
                if snap is None:
                    return self._json(404, {"error": "not found"})
                return self._json(200, snap)
            m = _match(api_path, "/test-jobs/*/telemetry")
            if m and method == "GET":
                snap = orchestrator.get_runtime_snapshot(m[0])
                if snap is None:
                    return self._json(404, {"error": "not found"})
                step = int(q.get("step", ["2"])[0])
                frm = int(q.get("from", ["120"])[0])
                ts = snap.get("timeseries")
                if ts is None:
                    job = db.get("test_jobs", m[0])
                    fm = (job or {}).get("final_metrics") or {}
                    return self._json(200, {"job_id": m[0], "aggregate": fm.get("aggregate"),
                                            "series": []})
                return self._json(200, {"job_id": m[0], "series": ts})
            m = _match(api_path, "/test-jobs/*/down")
            if m and method == "GET":
                snap = orchestrator.get_runtime_snapshot(m[0])
                if snap is None:
                    return self._json(404, {"error": "not found"})
                return self._json(200, {"job_id": m[0], "down": snap.get("down"),
                                        "observer": snap.get("observer"),
                                        "probe": snap.get("probe")})
            m = _match(api_path, "/test-jobs/*/observer")
            if m and method == "POST":
                import observer as _obs
                job = db.get("test_jobs", m[0])
                if not job:
                    return self._json(404, {"error": "not found"})
                plan = db.get("test_plans", job.get("test_plan_id") or "")
                tgt = db.get("targets", (plan or {}).get("target_id") or "")
                if not tgt:
                    return self._json(422, {"error": "target not resolvable from plan"})
                url = (tgt.get("canonical_origin") or "").rstrip("/") + "/"
                try:
                    report = _obs.verify_down(url, max_nodes=8, poll_timeout=30.0)
                except Exception as exc:
                    return self._json(502, {"error": "observer unreachable",
                                            "detail": str(exc)[:200]})
                out = report.to_dict()
                db.update("test_jobs", m[0], lambda j: j.update({"observer_verdict": out}),
                          actor=user, action="job.observer_check", resource_type="test_job",
                          reason=f"on-demand third-party verdict {out['verdict']}")
                return self._json(200, {"job_id": m[0], "observer": out})

            # ---- evidence (enriched dengan target/domain) ----
            if api_path == "/evidence" and method == "GET":
                out = []
                for e in db.list("evidence_bundles"):
                    e2 = dict(e)
                    job = db.get("test_jobs", e.get("job_id") or "")
                    plan = db.get("test_plans", (job or {}).get("test_plan_id") or "")
                    tgt = db.get("targets", (plan or {}).get("target_id") or "") if plan else None
                    e2["target_name"] = (tgt or {}).get("name")
                    e2["target_origin"] = (tgt or {}).get("canonical_origin")
                    e2["environment"] = (tgt or {}).get("environment")
                    e2["job_status"] = (job or {}).get("status")
                    e2["job_abort_code"] = (job or {}).get("abort_code")
                    out.append(e2)
                out.sort(key=lambda e: e.get("created_at") or "", reverse=True)
                return self._json(200, out)
            m = _match(api_path, "/evidence/*/verify")
            if m and method == "POST":
                ok, detail = evidence_mod.verify_evidence_bundle(m[0], actor=user)
                if ok is None:
                    return self._json(404, {"error": detail})
                return self._json(200, {"evidence_id": m[0], "verified": ok, "detail": detail})
            m = _match(api_path, "/evidence/*/build")
            if m and method == "POST":
                ev, note = evidence_mod.build_evidence_bundle(m[0], actor=user)
                if ev is None:
                    return self._json(404, {"error": note})
                return self._json(201, ev)
            m = _match(api_path, "/evidence/*/download")
            if m and method == "GET":
                ev = db.get("evidence_bundles", m[0])
                if not ev or not os.path.exists(ev["storage_uri"]):
                    return self._json(404, {"error": "bundle not found"})
                data = open(ev["storage_uri"], "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "application/gzip")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="evidence_{ev["job_id"]}.tar.gz"')
                self.send_header("Content-Length", str(len(data)))
                self._cors()
                self.end_headers()
                self.wfile.write(data)
                return

            # ---- webhooks (telemetry hooks) ----
            if api_path == "/webhooks" and method == "GET":
                import webhooks as _wh
                return self._json(200, _wh.list_hooks())
            if api_path == "/webhooks" and method == "POST":
                import webhooks as _wh
                b = self._body()
                hook, err = _wh.register(b.get("name"), b.get("url"),
                                         b.get("secret"), b.get("events"))
                if err:
                    return self._json(422, {"error": err})
                return self._json(201, hook)
            m = _match(api_path, "/webhooks/*/test")
            if m and method == "POST":
                import webhooks as _wh
                result, err = _wh.send_test(m[0])
                if err:
                    return self._json(404, {"error": err})
                return self._json(200, result)
            m = _match(api_path, "/webhooks/*")
            if m and method == "DELETE" and "/test" not in api_path:
                import webhooks as _wh
                return self._json(200, {"removed": _wh.remove(m[0])})
            if api_path == "/webhooks/deliveries" and method == "GET":
                import webhooks as _wh
                import db as _db
                dl = sorted(_db.list("webhook_deliveries"),
                            key=lambda d: d.get("at") or "", reverse=True)[:100]
                return self._json(200, dl)

            # ---- source capability registry (item 9) ----
            if api_path == "/sources/matrix" and method == "GET":
                import srccap as _sc
                return self._json(200, _sc.REGISTRY.matrix())
            if api_path == "/sources/pick" and method == "POST":
                import srccap as _sc
                b = self._body()
                src, why = _sc.REGISTRY.pick(b.get("required") or [], kind=b.get("kind"))
                if not src:
                    return self._json(409, {"error": "no source satisfies requirement",
                                            "required": b.get("required"), "reasons": why})
                return self._json(200, {"picked": src.to_dict(), "required": b.get("required")})
            if api_path == "/sources" and method == "GET":
                import srccap as _sc
                with SOURCES_LOCK:
                    items = [x.to_dict() for x in _sc.REGISTRY.list()]
                return self._json(200, {"sources": items,
                                        "capabilities": list(_sc.CAPABILITIES),
                                        "ssl_lib": _sc.ssl.OPENSSL_VERSION})
            if api_path == "/sources" and method == "POST":
                import srccap as _sc
                b = self._body()
                label = (b.get("label") or "").strip()
                if not label:
                    return self._json(422, {"error": {"field": "label", "message": "required"}})
                try:
                    src = _sc.REGISTRY.register(label, kind=b.get("kind") or "local",
                                                ip=b.get("ip"), region=b.get("region"),
                                                declared=b.get("declared"),
                                                note=b.get("note") or "")
                except _sc.SourceError as e:
                    return self._json(409, {"error": str(e)})
                try:
                    db.insert("sources", src.to_dict(), actor=user, action="source.registered",
                              resource_type="source", reason="label=%s kind=%s" % (label, src.kind))
                except Exception:
                    pass
                return self._json(201, src.to_dict())
            m = _match(api_path, "/sources/*/probe")
            if m and method == "POST":
                import srccap as _sc
                b = self._body()
                if not _sc.REGISTRY.get(m[0]):
                    return self._json(404, {"error": "source not found"})
                r = _sc.REGISTRY.probe(m[0], url=b.get("url") or _sc.DEFAULT_PROBE_URL)
                return self._json(200, {"source": m[0], "probe": r,
                                        "capabilities": _sc.REGISTRY.get(m[0]).capabilities()})
            m = _match(api_path, "/sources/*/udp")
            if m and method == "POST":
                import srccap as _sc
                import udp_probe as _up
                src = _sc.REGISTRY.get(m[0])
                if not src:
                    return self._json(404, {"error": "source not found"})
                b = self._body()
                r = _up.probe_all(qname=b.get("qname") or _up.DEFAULT_QNAME,
                                  qtype=b.get("qtype") or "TXT",
                                  timeout=float(b.get("timeout") or 3.0),
                                  ports_n=int(b.get("ports_n") or 6))
                if b.get("spoof", True):
                    r["spoof"] = _up.probe_spoof(qname=b.get("qname") or _up.DEFAULT_QNAME)
                if r.get("reflection_capable"):
                    _sc.mark_proven(m[0], ["udp"], {"udp": r})
                if (r.get("spoof") or {}).get("spoof_proven"):
                    _sc.mark_proven(m[0], ["spoof_src"], {"spoof": r["spoof"]})
                return self._json(200, dict(r, capabilities=src.capabilities()))
            m = _match(api_path, "/sources/*/remove")
            if m and method == "POST":
                import srccap as _sc
                gone = _sc.REGISTRY.remove(m[0])
                if not gone:
                    return self._json(404, {"error": "source not found"})
                return self._json(200, {"removed": m[0]})
            m = _match(api_path, "/sources/*")
            if m and method == "GET":
                import srccap as _sc
                src = _sc.REGISTRY.get(m[0])
                if not src:
                    return self._json(404, {"error": "source not found"})
                return self._json(200, src.to_dict(with_evidence=True))

            # ---- route override (Goal 3) ----
            if api_path == "/overrides" and method == "GET":
                with OVERRIDES_LOCK:
                    items = [{"id": o["id"], "spec": o["spec"].to_dict(),
                              "applied_tiers": o["report"].get("applied_tiers"),
                              "global_scope": o["report"].get("global_scope"),
                              "created_at": o["created_at"]} for o in OVERRIDES.values()]
                return self._json(200, sorted(items, key=lambda i: i["created_at"], reverse=True))
            if api_path == "/overrides" and method == "POST":
                import routeoverride as _ro
                b = self._body()
                domain = (b.get("domain") or "").strip().lower().strip(".")
                if not domain:
                    return self._json(422, {"error": {"field": "domain", "message": "required"}})
                mode = b.get("mode") or "404"
                if mode not in _ro.MODES:
                    return self._json(422, {"error": {"field": "mode",
                                                      "message": "must be one of %s" % sorted(_ro.MODES)}})
                spec = _ro.OverrideSpec(domain, paths=b.get("paths") or ["/*"], mode=mode,
                                        hosts=b.get("hosts") or [domain], note=b.get("note") or "")
                oid = gen_id("ovr")
                ro = _ro.RouteOverrider(spec, upstream=b.get("upstream"),
                                        connect_ip=b.get("connect_ip"),
                                        shim_port=int(b.get("shim_port") or 8899))
                report = ro.apply(tiers=tuple(b.get("tiers") or ("T2",)))
                with OVERRIDES_LOCK:
                    OVERRIDES[oid] = {"id": oid, "spec": spec, "ro": ro, "report": report,
                                      "created_at": now_iso(), "created_by": user}
                db.insert("overrides", {"id": oid, "domain": domain, "paths": spec.paths,
                                        "mode": mode, "tiers": report.get("applied_tiers"),
                                        "failed_tiers": report.get("failed_tiers"),
                                        "global_scope": report.get("global_scope"),
                                        "shim_url": (ro.shim.url_for("/") if ro.shim else None),
                                        "created_at": now_iso(), "created_by": user,
                                        "status": "ACTIVE"},
                          actor=user, action="override.applied", resource_type="override",
                          reason="tiers=%s mode=%s domain=%s" % (report.get("applied_tiers"), mode, domain))
                return self._json(201, dict(report, id=oid))
            m = _match(api_path, "/overrides/*/probe")
            if m and method == "POST":
                with OVERRIDES_LOCK:
                    rec = OVERRIDES.get(m[0])
                if not rec or rec["ro"].shim is None:
                    return self._json(404, {"error": "override or shim not found"})
                import transport as _tr
                b = self._body()
                path = b.get("path") or (rec["spec"].paths[0].rstrip("*") or "/")
                client = _tr.Transport(timeout=6)
                try:
                    resp = client.request(b.get("method", "GET"), rec["ro"].shim.url_for(path))
                finally:
                    client.close()
                return self._json(200, {"override_id": m[0], "path": path,
                                        "status": resp.status, "error": resp.error,
                                        "override_header": resp.header("x-galardo-override"),
                                        "forced": rec["spec"].matches(path),
                                        "shim": rec["ro"].shim.stats()})
            m = _match(api_path, "/overrides/*/revert")
            if m and method == "POST":
                with OVERRIDES_LOCK:
                    rec = OVERRIDES.pop(m[0], None)
                if not rec:
                    return self._json(404, {"error": "not found"})
                out = rec["ro"].revert()
                db.update("overrides", m[0], lambda o: o.update({"status": "REVERTED",
                                                                 "reverted_at": now_iso()}),
                          actor=user, action="override.reverted", resource_type="override",
                          reason="tiers=%s" % out.get("reverted"))
                return self._json(200, dict(out, id=m[0]))
            m = _match(api_path, "/overrides/*")
            if m and method == "GET" and len(m) == 1:
                with OVERRIDES_LOCK:
                    rec = OVERRIDES.get(m[0])
                if not rec:
                    return self._json(404, {"error": "not found"})
                return self._json(200, {"id": m[0], "created_at": rec["created_at"],
                                        "evidence": rec["ro"].evidence()})

            # ---- audit ----
            if api_path == "/audit" and method == "GET":
                events = db.list("audit_logs")
                events.sort(key=lambda e: e.get("occurred_at") or "", reverse=True)
                limit = int(q.get("limit", ["100"])[0])
                return self._json(200, events[:limit])

            return self._json(404, {"error": f"no route: {method} {api_path}"})
        except json.JSONDecodeError:
            return self._json(400, {"error": "malformed JSON"})
        except Exception as e:
            db.audit_event("api", "api.error", "route", path, reason=str(e)[:200])
            return self._json(500, {"error": "internal error", "detail": str(e)[:200]})


def _match(path, pattern):
    """Match /a/*/b style. Returns captured ids or None."""
    pp, lp = path.strip("/").split("/"), pattern.strip("/").split("/")
    if len(pp) != len(lp):
        return None
    ids = []
    for i, seg in enumerate(lp):
        if seg == "*":
            ids.append(pp[i])
        elif seg != pp[i]:
            return None
    return ids


def _g1(m):
    """Grup pertama dari hasil _match, tahan match-object maupun list."""
    if m is None:
        return None
    if hasattr(m, "group"):
        return m.group(1)
    try:
        return m[0]
    except Exception:
        return None


def _host_of(origin):
    try:
        from urllib.parse import urlsplit
        return urlsplit(origin).hostname or ""
    except Exception:
        return ""


def _claim_remote_job(worker_id):
    """Fleet scheduler extension: match a PENDING job whose plan explicitly opts in
    to remote k6 execution (plan.name contains 'k6' marker or dedicated flag).
    Returns a signed-shape envelope or None. The claiming worker is marked RUNNING.
    """
    plan_flag = (db.get("config", "remote_dispatch") or {}).get("enabled")
    if not plan_flag:
        return None
    jobs = db.list("test_jobs", lambda j: j.get("status") == "PENDING")
    for job in jobs:
        plan = db.get("test_plans", job.get("test_plan_id") or "")
        if not plan or not (plan.get("name", "") .lower().find("k6") >= 0 or plan.get("remote_dispatch")):
            continue
        scv = db.get("scenario_versions", plan.get("scenario_version_id") or "")
        tgt = db.get("targets", plan.get("target_id") or "")
        pol = db.get("safety_policies", plan.get("policy_version_id") or "")
        if not (scv and tgt and pol):
            continue
        from policy import effective_policy, load_policy_layers
        layers = load_policy_layers(db, plan.get("engagement_id"))
        layers.append(pol)
        eff, _ = effective_policy(layers)
        prof = scv["normalized_json"]["profile"]
        eff["max_rps"] = min(eff["max_rps"] or prof["max_rps"], prof["max_rps"])
        eff["max_vus"] = min(eff["max_vus"] or prof["virtual_users"], prof["virtual_users"])
        eff["max_duration_sec"] = min(eff["max_duration_sec"] or prof["duration_seconds"],
                                      prof["duration_seconds"])
        # reserve the job FIRST (single-claim guard): only one worker may hold it
        from orchestrator import _set_state
        moved = _set_state(job["id"], "DISPATCHING", actor="fleet-scheduler",
                           reason=f"claimed by remote worker {worker_id} (k6 envelope issued)")
        if not moved:
            continue  # another scheduler won the race
        envelope = {
            "job_id": job["id"],
            "correlation_id": job.get("correlation_id"),
            "scenario": scv["normalized_json"],
            "scenario_sha256": scv["content_sha256"],
            "effective_policy": eff,
            "target_origin": tgt["canonical_origin"],
            "issued_at": now_iso(),
            "worker": worker_id,
        }
        db.update("workers", worker_id, lambda x: x.update({
            "status": "RUNNING", "current_job_id": job["id"],
            "lease_expires_at": now_iso()}),
            actor=worker_id, action="worker.status", resource_type="worker",
            reason=f"claimed job {job['id']} (remote k6)")
        _set_state(job["id"], "RUNNING", actor="fleet-scheduler",
                   reason=f"remote k6 execution delegated to {worker_id}; "
                          f"caps rps={eff['max_rps']} vus={eff['max_vus']} dur={eff['max_duration_sec']}s")
        db.observation(job["id"], "orchestrator", "INFO",
                       f"job claimed by remote worker {worker_id} (k6 envelope issued)")
        return envelope
    return None


def overview():
    jobs = db.list("test_jobs")
    workers = db.list("workers")
    active = [j for j in jobs if j.get("status") in (
        "PENDING", "PREFLIGHT", "DISPATCHING", "RUNNING", "ABORT_REQUESTED", "ABORTING", "STOPPING", "RECOVERY_WAIT")]
    evs = db.list("evidence_bundles")
    obs = sorted(db.list("observations"), key=lambda o: o.get("observed_at") or "", reverse=True)[:20]
    return {
        "time": now_iso(),
        "platform_health": {"api": "HEALTHY", "db": "HEALTHY", "broker": "in-process (MVP)",
                            "safety_controller": "HEALTHY", "probe": "HEALTHY"},
        "job_counts": _count_by_status(jobs),
        "active_jobs": len(active),
        "workers": [{"id": w["id"], "status": w.get("status")} for w in workers] or
                   [{"id": "in-process-1", "status": "IDLE"}],
        "evidence": {"total": len(evs),
                     "verified": len([e for e in evs if e.get("status") in ("VERIFIED", "SEALED")])},
        "recent_observations": obs,
    }


def _count_by_status(jobs):
    out = {}
    for j in jobs:
        out[j.get("status", "?")] = out.get(j.get("status", "?"), 0) + 1
    return out


def serve(host="127.0.0.1", port=None):
    port = int(port or os.environ.get("GALARDO_API_PORT", "8090"))  # D12
    seed_lab()
    import fleet
    fleet.register_all()
    httpd = ThreadingHTTPServer((host, port), Handler)
    db.audit_event("api", "api.started", "service", "api", reason=f"listening on {host}:{port}")
    print(f"[galardo-api] listening on http://{host}:{port}  (dashboard: http://{host}:{port}/)")
    httpd.serve_forever()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=int(os.environ.get("GALARDO_API_PORT", "8090")))
    args = ap.parse_args()
    serve(args.host, args.port)
