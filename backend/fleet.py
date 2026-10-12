"""GALARDO - Worker fleet with capability/expertise scheduling (TD §7, Blueprint §8).

10 named workers, each with an expertise. The orchestrator picks workers whose
capabilities match scenario needs (weighted mix incl. POST-safe auth expert,
heavy payloads, long soak, high-concurrency burst, adaptive ramp, etc.).
One job = one worker slot (TD §7: a running worker takes no second job).
"""
from util import now_iso

FLEET = [
    {"id": "w01-smoke",    "name": "Smoke Sentinel",   "expertise": "smoke",
     "capabilities": ["GET", "light", "health-check"],
     "desc": "Uji cepat endpoint kritis; memastikan jalur dasar sehat sebelum beban naik."},
    {"id": "w02-ramp",     "name": "Ramp Rider",        "expertise": "ramp",
     "capabilities": ["GET", "ramp", "warmup"],
     "desc": "Spesialis ramp profile: menaikkan VU bertahap, mendeteksi titik degradasi awal."},
    {"id": "w03-burst",    "name": "Burst Breaker",     "expertise": "burst",
     "capabilities": ["GET", "POST", "burst", "high-concurrency"],
     "desc": "Lonjakan trafik mendadak (traffic spike, flash-crowd) dengan konkuensi tinggi."},
    {"id": "w04-soak",     "name": "Soak Surfer",       "expertise": "soak",
     "capabilities": ["GET", "long-duration", "steady"],
     "desc": "Durasi panjang (soak/endurance) untuk kebocoran memori & degradasi lambat."},
    {"id": "w05-spike",    "name": "Spike Scout",       "expertise": "spike",
     "capabilities": ["GET", "burst", "short-duration"],
     "desc": "Spike pendek & tajam; menguji elastisitas autoscaling dan reconnect."},
    {"id": "w06-auth",     "name": "Auth Ace",          "expertise": "auth-flow",
     "capabilities": ["GET", "POST-safe", "session", "auth-flow"],
     "desc": "Alur autentikasi aman (POST di bawah izin eksplisit), session & token placeholder."},
    {"id": "w07-heavy",    "name": "Payload Heavy",     "expertise": "heavy-payload",
     "capabilities": ["GET", "POST-safe", "large-response"],
     "desc": "Respons/payload besar: bandwidth, TTFB, dan streaming behavior."},
    {"id": "w08-mixed",    "name": "Mix Maestro",       "expertise": "mixed-routes",
     "capabilities": ["GET", "weighted-mix", "multi-route"],
     "desc": "Beberapa rute dengan weight berbeda dalam satu skenario (mis. 70/30)."},
    {"id": "w09-probe",    "name": "Probe Point",       "expertise": "probe-sync",
     "capabilities": ["GET", "health-check", "baseline"],
     "desc": "Sinkronisasi baseline probe & validasi health contract sebelum run berat."},
    {"id": "w10-chaos",    "name": "Chaos Cadet",       "expertise": "degradation-rehearsal",
     "capabilities": ["GET", "degradation-fixture", "safety-rehearsal"],
     "desc": "Rehearsal safety: memicu fixture degradasi untuk membuktikan jalur abort."},
]

REGISTRY = {}


def register_all():
    import db
    for w in FLEET:
        REGISTRY[w["id"]] = w
        existing = db.get("workers", w["id"])
        if not existing:
            db.insert("workers", {
                "id": w["id"], "name": w["name"], "expertise": w["expertise"],
                "capabilities": w["capabilities"], "desc": w["desc"],
                "version": "1.0", "status": "IDLE",
                "current_job_id": None, "last_heartbeat_at": now_iso(),
                "lease_expires_at": None, "created_at": now_iso(),
            }, actor="system", action="worker.registered", resource_type="worker",
                reason=f"expertise={w['expertise']}")


def heartbeat_all():
    import db
    for w in FLEET:
        if db.get("workers", w["id"]):
            db.update("workers", w["id"], lambda x: x.update({
                "last_heartbeat_at": now_iso()}), audit=False)


def set_status(worker_id, status, job_id=None):
    import db

    def mut(x):
        x["status"] = status
        x["current_job_id"] = job_id
        x["last_heartbeat_at"] = now_iso()
    db.update("workers", worker_id, mut, actor="orchestrator",
              action="worker.status", resource_type="worker",
              reason=f"-> {status}" + (f" job={job_id}" if job_id else ""))


def infer_required_capabilities(normalized):
    """Derive required capability tags from the compiled scenario."""
    caps = set()
    prof = normalized.get("profile") or {}
    dur = prof.get("duration_seconds") or 0
    vus = prof.get("virtual_users") or 1
    reqs = normalized.get("requests") or []
    methods = {r.get("method", "GET") for r in reqs}
    if len(reqs) > 1:
        caps.add("weighted-mix")
        caps.add("multi-route")
    if dur <= 30 and vus <= 4 and not prof.get("ramp"):
        caps.add("light")
        caps.add("health-check")
    if dur >= 300:
        caps.add("long-duration")
        caps.add("steady")
    if prof.get("ramp"):
        caps.add("ramp")
        if vus >= 10:
            caps.add("warmup")
    if vus >= 20 or (prof.get("max_rps") or 0) >= 100:
        caps.add("high-concurrency")
        caps.add("burst")
    if dur <= 15 and vus >= 10:
        caps.add("short-duration")
    if "POST" in methods:
        caps.add("POST-safe")
        caps.add("session")
        caps.add("auth-flow")
    if any((r.get("timeout_ms") or 0) >= 5000 for r in reqs):
        caps.add("large-response")
    if normalized.get("name", "").lower().find("degrad") >= 0 or normalized.get("name", "").lower().find("chaos") >= 0:
        caps.add("degradation-fixture")
        caps.add("safety-rehearsal")
    if not caps:
        caps.add("GET")
    return sorted(caps)


def pick_worker(normalized):
    """Score = |required ∩ capabilities| ; ties broken by IDLE-first then name."""
    import db
    required = set(infer_required_capabilities(normalized))
    best, best_score = None, -1
    for w in db.list("workers"):
        if w.get("status") not in ("IDLE",):
            continue
        score = len(required & set(w.get("capabilities") or []))
        if score > best_score:
            best, best_score = w, score
    return best, required, (best_score if best else 0)
