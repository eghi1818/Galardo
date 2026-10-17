"""GALARDO - External Webhook / Telemetry Hook (control-plane event forwarding).

Purpose: forward platform events (job lifecycle, safety aborts, evidence) to
monitoring/analytics systems owned by the operator - Grafana, Datadog, SIEM,
internal dashboards. Outbound DATA export only; it carries no traffic-routing
capability (routing stays identity-sim + fleet, per PRD addendum).

Security:
- HMAC-SHA256 signature header (X-Galardo-Signature: sha256=<hex>) per delivery
- delivery log (append-only) with status/latency per attempt
- SSRF guard: cloud metadata endpoints (169.254.0.0/16, 100.100.100.200) rejected
- dispatch is non-blocking (background thread, 2 retries w/ backoff)
"""
import hashlib
import hmac
import ipaddress
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from util import now_iso, gen_id

MAX_BODY = 65536
BLOCKED_NETS = [ipaddress.ip_network(n) for n in
                ("169.254.0.0/16", "100.100.100.200/32")]  # cloud metadata
EVENT_TYPES = ("job.completed", "job.aborted", "job.failed", "job.recovery",
               "safety.abort", "evidence.created", "hook.ping")


def _validate_url(url):
    """Basic SSRF guard: scheme + metadata-IP rejection. Returns error or None."""
    try:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https"):
            return "scheme must be http/https"
        host = parts.hostname or ""
        try:
            ip = ipaddress.ip_address(host)
            for net in BLOCKED_NETS:
                if ip in net:
                    return f"endpoint {host} is a blocked metadata address"
        except ValueError:
            pass  # hostname, resolved at delivery time
        return None
    except Exception as e:
        return f"invalid url: {e}"


def register(name, url, secret, events):
    import bus
    import db
    err = _validate_url(url)
    if err:
        return None, err
    events = [e for e in (events or list(EVENT_TYPES)) if e in EVENT_TYPES] or list(EVENT_TYPES)
    hook = {"id": gen_id("wh"), "name": name or "hook", "url": url,
            "secret": secret, "events": events, "status": "ACTIVE",
            "created_at": now_iso()}
    db.insert("webhooks", hook, actor="operator", action="webhook.registered",
              resource_type="webhook", reason=f"events={events} url={url}")
    return hook, None


def list_hooks():
    import db
    return db.list("webhooks")


def remove(hook_id):
    import db
    return db.delete("webhooks", hook_id, actor="operator", action="webhook.removed")


def _deliver(hook, event_type, payload, delivery_id):
    import db
    body = json.dumps({"event": event_type, "sent_at": now_iso(), "data": payload},
                      sort_keys=True).encode()
    sig = hmac.new(hook["secret"].encode(), body, hashlib.sha256).hexdigest()
    attempts = []
    ok = False
    for attempt in (1, 2, 3):
        t0 = time.time()
        try:
            req = urllib.request.Request(
                hook["url"], data=body, method="POST",
                headers={"Content-Type": "application/json",
                         "X-Galardo-Event": event_type,
                         "X-Galardo-Delivery": delivery_id,
                         "X-Galardo-Signature": f"sha256={sig}",
                         "User-Agent": "galardo-webhook/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                code = r.status
            ok = code == 200
            attempts.append({"attempt": attempt, "status": code,
                             "ms": round((time.time() - t0) * 1000)})
            break
        except urllib.error.HTTPError as e:
            attempts.append({"attempt": attempt, "status": e.code,
                             "ms": round((time.time() - t0) * 1000)})
            if e.code < 500:  # 4xx = permanent, don't retry
                break
        except Exception as e:
            attempts.append({"attempt": attempt, "error": str(e)[:120],
                             "ms": round((time.time() - t0) * 1000)})
        time.sleep(1.5 * attempt)
    db.insert("webhook_deliveries", {
        "id": delivery_id, "hook_id": hook["id"], "hook_name": hook["name"],
        "event": event_type, "ok": ok, "attempts": attempts,
        "payload_sha256": hashlib.sha256(body).hexdigest(),
        "at": now_iso()})
    return ok


def fire(event_type, payload):
    """Non-blocking dispatch ke semua hook ACTIVE yang berlangganan event_type.
    Tidak pernah melempar. Juga menerbitkan ke bus NATS dan mengevaluasi aturan alert."""
    delivered = []
    try:
        if event_type not in EVENT_TYPES:
            return
        import db
        hooks = [h for h in db.list("webhooks")
                 if h.get("status") == "ACTIVE" and event_type in h.get("events", [])]
        for hook in hooks:
            delivery_id = gen_id("dlv")
            delivered.append({"hook": hook.get("id"), "delivery": delivery_id})
            threading.Thread(target=_deliver, args=(hook, event_type, payload, delivery_id),
                             daemon=True, name="wh-" + str(hook.get("id"))).start()
    except Exception:
        pass
    try:
        bus.publish(event_type, {"event": event_type, "deliveries": delivered, "payload": payload})
    except Exception:
        pass
    try:
        import alerts
        alerts.run(event_type, payload)
    except Exception:
        pass

def send_test(hook_id):
    import db
    hook = db.get("webhooks", hook_id)
    if not hook:
        return None, "hook not found"
    delivery_id = gen_id("dlv")
    ok = _deliver(hook, "hook.ping",
                  {"message": "Galardo webhook test", "hook": hook["name"]}, delivery_id)
    dlv = db.get("webhook_deliveries", delivery_id)
    return {"ok": ok, "delivery": dlv}, None


def verify_signature_example():
    return ("X-Galardo-Signature: sha256=HMAC_SHA256(secret, raw_body). "
            "Verify: hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()")
