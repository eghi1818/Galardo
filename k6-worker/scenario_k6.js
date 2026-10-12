// galardo-k6/scenario_k6.js — k6 executor consuming a Galardo job envelope.
// Envelope: __ENV.GALARDO_JOB = {job_id, scenario(normalized), effective_policy,
// target_origin, scenario_sha256}. Target resolved server-side; caps enforced
// BOTH here (arrival-rate) and server-side by the orchestrator policy engine.
//
// Rate model: if scenario.profile.max_rps is set, a ramping-arrival-rate
// executor converts the VU ramp into proportional target rates (strict cap).
// Otherwise falls back to stage-less VU execution.
//
// Smoke override: GALARDO_DURATION_CAP (seconds) shrinks total duration for
// pipeline verification without touching the immutable scenario version.

import http from 'k6/http';
import { check, sleep } from 'k6';

const _raw = __ENV.GALARDO_JOB || '{}';
const job = JSON.parse(_raw);
const norm = job.scenario || { profile: {}, requests: [], think_time_ms: {} };
const eff = job.effective_policy || {};

const TOTAL_WEIGHT = (norm.requests || []).reduce((a, r) => a + (r.weight || 100), 0);
const DUR_CAP = Number(__ENV.GALARDO_DURATION_CAP || 0);
const BASE_RPS = Math.min(norm.profile.max_rps || 0, eff.max_rps || Infinity);
const RAMP = ((norm.profile || {}).ramp || []).slice().sort((a, b) => a.after_seconds - b.after_seconds);
// rate scaling anchor = peak of the RAMP (not profile.virtual_users, which is a
// pre-ramp capacity hint). Peak ramp == intended peak concurrency of the test.
const MAX_RAMP_VU = RAMP.length ? Math.max.apply(null, RAMP.map(function (r) { return r.virtual_users || 0; })) : (norm.profile.virtual_users || 1);

function buildStages(totalSec) {
  if (!RAMP.length) return [{ from: 0, to: totalSec, vu: Math.min(norm.profile.virtual_users || 1, MAX_RAMP_VU) }];
  const first = RAMP[0];
  const seg = [];
  // implicit stage from t=0 to first ramp point at first.virtual_users
  if (first.after_seconds > 0) {
    seg.push({ from: 0, to: first.after_seconds, vu: first.virtual_users });
  }
  let prev = first;
  for (const r of RAMP.slice(1)) {
    const at = Math.min(r.after_seconds, totalSec);
    if (at > prev.after_seconds) {
      seg.push({ from: prev.after_seconds, to: at, vu: prev.virtual_users });
      prev = r;
    } else if (at === prev.after_seconds) {
      prev = r;
    }
  }
  if (prev.after_seconds < totalSec) {
    seg.push({ from: prev.after_seconds, to: totalSec, vu: Math.min(prev.virtual_users, MAX_RAMP_VU) });
  }
  return seg;
}

const totalDuration = DUR_CAP > 0 ? Math.min(DUR_CAP, norm.profile.duration_seconds || 1) : (norm.profile.duration_seconds || 1);

let options;
if (BASE_RPS > 0) {
  // rate-based: map ramp VU -> proportional rate (strict max_rps ceiling)
  const stages = buildStages(totalDuration).map(s => ({
    duration: `${Math.max(1, s.to - s.from)}s`,
    target: Math.max(1, Math.round(BASE_RPS * (s.vu / MAX_RAMP_VU))),
  }));
  options = {
    discardResponseBodies: true,
    summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(50)', 'p(95)', 'p(99)'],
    thresholds: {
      'http_req_failed': ['rate<0.60'], // advisory ceiling; safety abort handled by orchestrator
    },
    scenarios: {
      galardo_rate: {
        executor: 'ramping-arrival-rate',
        startRate: stages[0]?.target || 1,
        timeUnit: '1s',
        preAllocatedVUs: Math.max(20, Math.min(600, Math.round(BASE_RPS * 2))),
        maxVUs: Math.max(50, Math.min(2000, Math.round(BASE_RPS * 4))),
        stages,
      },
    },
  };
} else {
  options = {
    discardResponseBodies: true,
    summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(50)', 'p(95)', 'p(99)'],
    vus: 1,
    duration: `${totalDuration || 1}s`,
    thresholds: { 'http_req_failed': ['rate<0.60'] },
  };
}

export { options };

const BASE = job.target_origin;
// ---- identity simulation (PRD addendum: Edge Client Simulation) ----
// Header-level synthetic identities only; TCP source = this worker VM.
const IDSIM = norm.identity_sim && norm.identity_sim.enabled ? norm.identity_sim : null;
let ID_POOL = null;
if (IDSIM) {
  // pool via file (GALARDO_ID_POOL_FILE) to dodge ARG_MAX; fallback inline env
  if (__ENV.GALARDO_ID_POOL_FILE) {
    ID_POOL = JSON.parse(open(__ENV.GALARDO_ID_POOL_FILE));
  } else {
    ID_POOL = JSON.parse(__ENV.GALARDO_ID_POOL || '[]');
  }
  if (!ID_POOL.length) {
    // fallback: derive inline from seed via deterministic LCG (no big env)
    ID_POOL = [];
    let s = 0;
    for (const c of String(IDSIM.seed || 'default-seed')) s = (s * 131 + c.charCodeAt(0)) >>> 0;
    for (let i = 0; i < IDSIM.count; i++) {
      s = (s * 1103515245 + 12345) >>> 0;
      const oct = [];
      for (let o = 0; o < 4; o++) { s = (s * 1103515245 + 12345) >>> 0; oct.push(2 + (s % 251)); }
      ID_POOL.push({ ip: oct.join('.'), session: 'sess-' + i });
    }
  }
}
let ID_CURSOR = 0;
function nextIdentity() {
  if (!IDSIM || !ID_POOL.length) return null;
  if (IDSIM.churn === 'per-iteration') {
    ID_CURSOR = (ID_CURSOR + 1) % ID_POOL.length;   // new identity every request
    return ID_POOL[ID_CURSOR];
  }
  return ID_POOL[__VU % ID_POOL.length];            // sticky per VU
}

const THINK_MIN = (norm.think_time_ms?.min || 0) / 1000;
const THINK_MAX = (norm.think_time_ms?.max || 0) / 1000;

function pickRequest() {
  let x = Math.random() * TOTAL_WEIGHT, acc = 0;
  for (const r of norm.requests) {
    acc += r.weight || 100;
    if (x <= acc) return r;
  }
  return norm.requests[norm.requests.length - 1];
}

export default function () {
  const r = pickRequest();
  const ident = nextIdentity();
  const params = {
    timeout: `${Math.min(r.timeout_ms || 4000, 10000)}ms`,
    headers: Object.assign({
      'User-Agent': `galardo-k6/1.0 (authorized; job=${job.job_id}; sha=${(job.scenario_sha256 || '').slice(0, 12)})`,
    }, r.headers || {}),
  };
  if (ident) {
    if (IDSIM.path === 'direct') {
      params.headers['CF-Connecting-IP'] = ident.ip;
      params.headers['X-Forwarded-For'] = ident.ip;
    } else {
      params.headers['X-Client-Id'] = ident.ip;  // edge-safe identity carrier
    }
    params.headers['X-Session-Id'] = ident.session;
  }
  // connection mode: identity_sim default = churn (no-keep-alive) untuk menekan
  // session table; Keep-Alive toggle (KA=true env ATAU scenario.keep_alive) untuk
  // memisahkan kegagalan "koneksi baru" vs "kapasitas aplikasi" (Improvement A1).
  const KA = (__ENV.GALARDO_KEEP_ALIVE === 'true') || norm.keep_alive === true;
  const transportOpts = {};
  if (IDSIM && !KA) transportOpts['no-keep-alive'] = true;   // churn mode
  const res = http.request(r.method || 'GET', `${BASE}${r.path}`, null,
    Object.assign(params, transportOpts));
  check(res, { 'status<400': (x) => x.status < 400 });
  if (THINK_MAX > 0) sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN));
}

export function handleSummary(data) {
  const m = data.metrics;
  const dur = m.http_req_duration?.values || {};
  const out = {
    job_id: job.job_id,
    scenario_sha256: job.scenario_sha256,
    generator: 'k6',
    identity_sim: IDSIM ? { count: IDSIM.count, churn: IDSIM.churn, header: IDSIM.header, pool_size: ID_POOL ? ID_POOL.length : 0 } : null,
    requests: m.http_reqs?.values?.count || 0,
    rps: m.http_reqs?.values?.rate || 0,
    duration_s: Math.round((data.state?.testRunDurationMs || 0)) / 1000,
    p50_ms: dur['p(50)'] ?? dur.med ?? null,
    p95_ms: dur['p(95)'] ?? null,
    p99_ms: dur['p(99)'] ?? null,
    avg_ms: dur.avg ?? null,
    failed_rate: m.http_req_failed?.values?.rate || 0,
    bytes_recv: m.data_received?.values?.count || 0,
  };
  return {
    stdout: `\nGALARDO_ENVELOPE_RESULT ${JSON.stringify(out, null, 1)}\n`,
  };
}
