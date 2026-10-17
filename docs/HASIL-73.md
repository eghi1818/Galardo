# HASIL-73 - e2e jalur lokal (item 10, bagian 1)

Tanggal: 2026-10-17 22:17:46 WIB
HEAD   : b1a4b87

## Ringkasan exit code
```
rc=0 :: smoke.sh
rc=0 :: make demo (GOAL 2 DOWN+recovery, GOAL 3 404/blank)
rc=0 :: make own1 (offline dns_txt)
rc=0 :: make crypto (RFC 8032)
rc=0 :: make trust (kebijakan antar-node)
rc=0 :: make peer (peer-list)
rc=0 :: make capacity
rc=0 :: make srccap
rc=0 :: make backup-verify
rc=0 :: make docker-verify
```

## Output mentah
```
### health
GET /health -> 404
### /me dengan token
GET /me -> 404
### /me tanpa token
GET /me -> 404

### smoke.sh
== SMOKE: import + startup ==
  [v] import ok: backend/step_load.py
  [v] import ok: backend/cachebuster.py
  [v] import ok: backend/ownership_ladder.py
== SMOKE: step_load benar-benar jalan ==
  [v] step_load jalan
== SMOKE OK ==
---

### make demo (GOAL 2 DOWN+recovery, GOAL 3 404/blank)
python3 tools/galardo_demo.py
==============================================================
 GALARDO DEMO - GOAL 2 (DOWN + recovery) + GOAL 3 (404/blank)
==============================================================
target http://127.0.0.1:18097 | workers=16 heavy=150ms vus=300 dur=45s
  [target] hidup di http://127.0.0.1:18097
  [baseline] p50 idle 0.74 ms (10 sampel, 0.0s)
  [plafon] workers=16 backlog=0
  [probe] out-of-band jalan (interval 0.4s timeout 1.0s)
    [TRANSISI] UP        -> SUSPECT    fail_streak=3 >= 3 (timeout after 1.00s)
    [TRANSISI] SUSPECT   -> DOWN       sustained failure 4.04s >= 4.00s
  [spike] 4743 req / 46.0s = 103 rps | p50 2911ms p95 2926ms | 4xx 0 5xx 0
    [TRANSISI] DOWN      -> RECOVERING ok_streak=3 >= 3
    [TRANSISI] RECOVERING -> RECOVERED  stable 3.22s
  [verdict] state=RECOVERED down_verified=True ttr=43.864 transisi=4
  [bukti-jenuh] peak_waiting=288 avg_wait_ms=2631.05 saturated=True
  [goal3-404] applied=['T2'] status=404 forced=True
  [goal3-blank] applied=['T2'] status=200 body_len=0 forced=True
  [goal3-revert] reverted=['T2'] / ok
--------------------------------------------------------------
{
  "steps": [
    {
      "step": "target",
      "detail": "hidup di http://127.0.0.1:18097"
    },
    {
      "step": "baseline",
      "detail": "p50 idle 0.74 ms (10 sampel, 0.0s)"
    },
    {
      "step": "plafon",
      "detail": "workers=16 backlog=0"
    },
    {
      "step": "probe",
      "detail": "out-of-band jalan (interval 0.4s timeout 1.0s)"
    },
    {
      "step": "spike",
      "detail": "4743 req / 46.0s = 103 rps | p50 2911ms p95 2926ms | 4xx 0 5xx 0"
    },
    {
      "step": "verdict",
      "detail": "state=RECOVERED down_verified=True ttr=43.864 transisi=4"
    },
    {
      "step": "bukti-jenuh",
      "detail": "peak_waiting=288 avg_wait_ms=2631.05 saturated=True"
    },
    {
      "step": "goal3-404",
      "detail": "applied=['T2'] status=404 forced=True"
    },
    {
      "step": "goal3-blank",
      "detail": "applied=['T2'] status=200 body_len=0 forced=True"
    },
    {
      "step": "goal3-revert",
      "detail": "reverted=['T2'] / ok"
    }
  ],
  "verdict": {
    "state": "RECOVERED",
    "down_verified": true,
    "time_to_recover": 43.864,
    "samples_total": 64,
    "error_ratio_pct": 71.88,
    "transitions": [
      {
        "from": "UP",
        "to": "SUSPECT",
        "reason": "fail_streak=3 >= 3 (timeout after 1.00s)",
        "at": 1792250183.014987,
        "at_iso": "2026-10-17T15:16:23Z"
      },
      {
        "from": "SUSPECT",
        "to": "DOWN",
        "reason": "sustained failure 4.04s >= 4.00s",
        "at": 1792250187.052525,
        "at_iso": "2026-10-17T15:16:27Z"
      },
      {
        "from": "DOWN",
        "to": "RECOVERING",
        "reason": "ok_streak=3 >= 3",
        "at": 1792250227.698303,
        "at_iso": "2026-10-17T15:17:07Z"
      },
      {
        "from": "RECOVERING",
        "to": "RECOVERED",
        "reason": "stable 3.22s",
        "at": 1792250230.9163032,
        "at_iso": "2026-10-17T15:17:10Z"
      }
    ]
  },
  "gate": {
    "workers": 16,
    "backlog": 0,
    "inflight": 0,
    "waiting": 0,
    "peak_inflight": 16,
    "peak_waiting": 288,
    "served": 5046,
    "shed_503": 0,
    "avg_wait_ms": 2631.05,
    "saturated": true
  },
  "override": {
    "404": {
      "status": 404,
      "override_header": "404",
      "body_len": 0,
      "forced": true,
      "latency_ms": 2.86,
      "url": "http://127.0.0.1:18779/blocked/xyz",
      "matches_spec
--------------------------------------------------------------
DEMO_OK
---

### make own1 (offline dns_txt)
python3 tests/test_ownership_rung1.py
== A. challenge dan label ==
  ok   A record_name pakai label utama
  ok   A expected_value format baku
  ok   A label legacy diterima
  ok   A record_name bersih dari titik
== B. quorum cukup -> proof nyata ==
  ok   B proof ok
  ok   B label tercatat
  ok   B record tercatat
  ok   B verified_at terisi
  ok   B token diteruskan ke resolver
  ok   B adapt -> rank 4
  ok   B adapt -> method dns_txt
  ok   B adapt -> is_proof
  ok   B gate lolos
  ok   B cukup untuk min well_known_file
  ok   B attestasi tidak cukup untuk dns_txt
== C. quorum tidak cukup -> fail-closed ==
  ok   C proof gagal
  ok   C evidence mencatat percobaan per label
  ok   C ladder_proof gagal
  ok   C gate menolak
== D. jatuh ke label legacy ==
  ok   D lolos lewat label legacy
== E. challenge kedaluwarsa ==
  ok   E kedaluwarsa -> gagal
  ok   E alasan eksplisit
== F. tingkat bukti dan min_level ==
  ok   F min_level asing ditolak
  ok   F LEVELS terurut kuat ke lemah
== G. sidik jari ==
  ok   G stabil
  ok   G beda antar method

RESULTS: 26 passed, 0 failed
---

### make crypto (RFC 8032)
==============================================================
  VERIFIKASI TIER 1 — ED25519 (RFC 8032) + ENVELOPE
==============================================================

--- A. Vektor known-answer RFC 8032 ---
  PASS  A publickey TEST 1 (pesan kosong)
  PASS  A signature TEST 1 (pesan kosong)
  PASS  A verify TEST 1 (pesan kosong)
  PASS  A verify tolak pesan diubah TEST 1 (pesan kosong)
  PASS  A verify tolak S >= L TEST 1 (pesan kosong)
  PASS  A verify tolak public key salah TEST 1 (pesan kosong)
  PASS  A verify tolak tanda tangan diubah TEST 1 (pesan kosong)
  PASS  A publickey TEST 2 (1 byte)
  PASS  A signature TEST 2 (1 byte)
  PASS  A verify TEST 2 (1 byte)
  PASS  A verify tolak pesan diubah TEST 2 (1 byte)
  PASS  A verify tolak S >= L TEST 2 (1 byte)
  PASS  A verify tolak public key salah TEST 2 (1 byte)
  PASS  A verify tolak tanda tangan diubah TEST 2 (1 byte)
  PASS  A publickey TEST 3 (2 byte)
  PASS  A signature TEST 3 (2 byte)
  PASS  A verify TEST 3 (2 byte)
  PASS  A verify tolak pesan diubah TEST 3 (2 byte)
  PASS  A verify tolak S >= L TEST 3 (2 byte)
  PASS  A verify tolak public key salah TEST 3 (2 byte)
  PASS  A verify tolak tanda tangan diubah TEST 3 (2 byte)
  PASS  A verify tolak panjang tanda tangan salah
  PASS  A verify tolak panjang pk salah

--- B. Semantik envelope + kanonik ---
  PASS  B canonical urut + tanpa spasi
  PASS  B canonical deterministik
  PASS  B canonical beda untuk payload beda
  PASS  B roundtrip envelope sah
  PASS  B kid envelope = hash pk
  PASS  B tolak payload diubah
  PASS  B tolak nonce diubah
  PASS  B tolak kid diubah (jadi tak dikenal)
  PASS  B penerimaan pertama lolos
  PASS  B replay nonce ditolak
  PASS  B tolak envelope terlalu tua
  PASS  B tolak envelope dari masa depan
  PASS  B tolak key id tak dikenal
  PASS  B tolak kunci yang salah
  PASS  B tolak non-object
  PASS  B tolak envelope rusak
  PASS  B tolak sig bukan base64
  PASS  B tolak versi asing
  PASS  B tolak nonce terlalu pendek
  PASS  B tanpa cache replay envelope tetap sah

--- C. Persistensi keyring ---
  PASS  C keyring mengembalikan kid 16 hex
  PASS  C file keyring ditulis
  PASS  C mode file keyring 600
  PASS  C muat ulang melihat kunci
  PASS  C secret identik setelah muat ulang
  PASS  C public_map tanpa secret
  PASS  C tanda tangan lintas muat ulang terverifikasi

--- D. Kinerja ---
  INFO  sign 2.2 ms/op, verify 2.5 ms/op (pure python)
  PASS  D sign di bawah 200 ms
  PASS  D verify di bawah 200 ms

==============================================================
RESULTS: 52 passed, 0 failed
==============================================================
---

### make trust (kebijakan antar-node)
==============================================================
  VERIFIKASI TIER 1 — KEBIJAKAN KEPERCAYAAN ANTAR-NODE
==============================================================

--- A. Mode off/warn/enforce + replay + role ---
  PASS  A off terima payload mentah
  PASS  A warn terima tanpa tanda tangan
  PASS  A warn menghitung unsigned
  PASS  A warn terima kid tak dikenal tapi menandai
  PASS  A enforce tolak tanpa tanda tangan
  PASS  A enforce tolak kid tak dikenal
  PASS  A enforce terima yang sah
  PASS  A enforce tolak replay
  PASS  A replay tercatat
  PASS  A enforce tolak payload diubah
  PASS  A enforce tolak kedaluwarsa
  PASS  A role worker dikenali
  PASS  A role salah ditolak
  PASS  A mode off meloloskan role apa pun
  PASS  A mode asing jatuh ke warn
  PASS  A wrap tanpa secret menghasilkan sig kosong
  PASS  A envelope tanpa secret tetap punya nonce dan ts
  PASS  A enforce tolak envelope tanpa sig
  PASS  A unsigned terhitung di stats

--- B. Cache replay + persistensi peer ---
  PASS  B nonce baru diterima
  PASS  B nonce sama ditolak
  PASS  B batas ukuran memicu pemangkasan
  PASS  B hits tercatat
  PASS  B entri kedaluwarsa dipangkas
  PASS  B peer tersimpan
  PASS  B peer muat ulang terlihat
  PASS  B role ikut tersimpan
  PASS  B public_map benar
  PASS  B peers.json tanpa secret

--- C. END-TO-END lewat TCP ---
  PASS  C pesan sah diterima (200)
  PASS  C balasan server terverifikasi klien
  PASS  C balasan server bertanda tangan
  PASS  C rogue ditolak (401)
  PASS  C tamper ditolak (401)
  PASS  C replay ditolak (401)
  PASS  C tanpa tanda tangan ditolak (401)
  PASS  C penolakan server tercatat
  PASS  C mode warn menerima tanpa tanda tangan (200)
  PASS  C server memakai kid sendiri saat membalas
  INFO  mode=enforce accepted=1 rejected=4 unsigned=2 warned=3 replayed=1 replay_cache=1
  INFO  mode=enforce accepted=1 rejected=0 unsigned=0 warned=0 replayed=0 replay_cache=1

==============================================================
RESULTS: 39 passed, 0 failed
==============================================================
---

### make peer (peer-list)
(kosong)
---

### make capacity
GALARDO_CAP_STEPS=25,50,100 GALARDO_CAP_WORKERS=0 python3 tools/galardo_capacity.py
====================================================================
 GALARDO CAPACITY DISCOVERY
 target=http://127.0.0.1:18096 path=/healthz steps=[25, 50, 100] 8s/step workers=unlimited
====================================================================
  VUs    rps       p50ms     p95ms     err%    
  25     4906.8    3.5       10.4      0.00    
  50     4987.2    7.1       19.7      0.00    
  100    4438.2    14.7      42.7      0.00    
--------------------------------------------------------------------
 plafon terukur: 4987 rps (GENERATOR laptop)
 KNEE ditemukan di 100 VU (4438 rps) - sebab: rps tidak naik 2 langkah berturut-turut
 Rekomendasi spike: 130 VU, target ~5770 rps (realistis ~4987 rps)
 PERHATIAN: target rps di atas plafon generator laptop ini (4987 rps)
 CATATAN: workers=0 -> ini plafon GENERATOR, bukan target.
          ulangi dengan CAP_WORKERS=<n> untuk plafon target.
--------------------------------------------------------------------
{
  "target": "http://127.0.0.1:18096",
  "path": "/healthz",
  "workers": 0,
  "steps": [
    {
      "vus": 25,
      "seconds": 9.1,
      "requests": 44467,
      "rps": 4906.8,
      "p50_ms": 3.5,
      "p95_ms": 10.4,
      "err_4xx": 0,
      "err_5xx": 0,
      "error_pct": 0.0,
      "conn_errors": 0,
      "timeouts": 0
    },
    {
      "vus": 50,
      "seconds": 9.1,
      "requests": 45338,
      "rps": 4987.2,
      "p50_ms": 7.1,
      "p95_ms": 19.7,
      "err_4xx": 0,
      "err_5xx": 0,
      "error_pct": 0.0,
      "conn_errors": 0,
      "timeouts": 0
    },
    {
      "vus": 100,
      "seconds": 9.1,
      "requests": 40272,
      "rps": 4438.2,
      "p50_ms": 14.7,
      "p95_ms": 42.7,
      "err_4xx": 0,
      "err_5xx": 0,
      "error_pct": 0.0,
      "conn_errors": 0,
      "timeouts": 0
    }
  ],
  "baseline": {
    "vus": 25,
    "seconds": 9.1,
    "requests": 44467,
    "rps": 4906.8,
    "p50_ms": 3.5,
    "p95_ms": 10.4,
    "err_4xx": 0,
    "err_5xx": 0,
    "error_pct": 0.0,
    "conn_errors": 0,
    "timeouts": 0
  },
  "knee": {
    "vus": 100,
    "rps": 4438.2,
    "p95_ms": 42.7,
    "reason": "rps tidak naik 2 langkah berturut-turut"
  },
  "max_rps_observed": 4987.2,
  "ceiling_kind": "generator",
  "recommendation": {
    "spike_vus": 130,
    "spike_rps_target": 5769.7,
    "spike_rps_expected": 4987.2,
    "capped_by_generator": true,
    "note": "spike 1,2-1,5x knee; kalau tidak DOWN -> naikkan 2x lagi | PERHATIAN: rps di atas 4987 tidak bisa dicapai laptop ini"
  }
}
CAPACITY_OK
---

### make srccap
python3 tools/galardo_srccap.py
probe target: https://koler.space/
------------------------------------------------------------
sumber     : src-local-laptop (local)
proven     : ['http1', 'keepalive', 'tls12', 'udp']
unproven   : ['ipv6']
na (lib)   : ['http2', 'tls13', 'tls13_lib']
declared   : ['datacenter', 'high_concurrency']
kapabilitas: ['datacenter', 'high_concurrency', 'http1', 'keepalive', 'tls12', 'udp']
lib ssl    : LibreSSL 2.8.3
bukti:
   http1      {"ok": true, "ms": 1215.6, "status": 200, "proto": 11}
   keepalive  {"ok": true, "reused_socket": true, "status": [200, 200]}
   tls13      {"ok": null, "reason": "lib_tidak_mendukung", "lib": "LibreSSL 2.8.3", "error": "Unsupported protocol version 0x304"}
   tls12      {"ok": true, "negotiated": "TLSv1.2", "cipher": "ECDHE-ECDSA-CHACHA20-POLY1305", "lib": "LibreSSL 2.8.3"}
   ipv6       {"ok": false, "addresses": ["::ffff:104.21.30.27", "::ffff:172.67.150.112"], "real_v6": [], "ipv4_mapped": ["::ffff:104.
------------------------------------------------------------
uji pick():
   butuh http1,tls13                        -> TIDAK ADA | src-local-laptop kurang: tls13
   butuh http1,udp                          -> src-local-laptop 
   butuh http1,spoof_src,residential        -> TIDAK ADA | src-local-laptop kurang: residential, spoof_src
------------------------------------------------------------
{
  "capabilities": [
    "http1",
    "http2",
    "tls12",
    "tls13",
    "keepalive",
    "redirects",
    "ipv6",
    "udp",
    "spoof_src",
    "residential",
    "datacenter",
    "high_concurrency"
  ],
  "ssl_lib": "LibreSSL 2.8.3",
  "sources": {
    "src-local-laptop": [
      "datacenter",
      "high_concurrency",
      "http1",
      "keepalive",
      "tls12",
      "udp"
    ]
  },
  "not_applicable": {
    "src-local-laptop": [
      "http2",
      "tls13",
      "tls13_lib"
    ]
  },
  "gaps": {
    "http1": [],
    "http2": [
      "src-local-laptop"
    ],
    "tls12": [],
    "tls13": [
      "src-local-laptop"
    ],
    "keepalive": [],
    "redirects": [
      "src-local-laptop"
    ],
    "ipv6": [
      "src-local-laptop"
    ],
    "udp": [],
    "spoof_src": [
      "src-local-laptop"
    ],
    "residential": [
      "src-local-laptop"
    ],
    "datacenter": [],
    "high_concurrency": []
  }
}
SRCCAP_OK
---

### make backup-verify
python3 tools/verify_backup.py
== A. cakupan file ==
  ok   A data/ ikut
  ok   A HASIL-* ikut
  ok   A SESSION_STATE ikut
  ok   A dokumen lain diabaikan
== B. arsip + manifest ==
  ok   B arsip dibuat
  ok   B ada MANIFEST.json
  ok   B arsip memuat data/state.json
  ok   B sha256 manifest benar
  ok   B count cocok
== C. retensi ==
  ok   C retensi menyisakan 2
== D. restore ==
  ok   D isi file pulih identik
  ok   D manifest tidak ditulis
  ok   D tanpa --force tidak menimpa
  ok   D dengan --force menimpa

RESULTS: 14 passed, 0 failed
---

### make docker-verify
python3 tools/verify_compose.py
== A. Dockerfile ==
  ok   A ada Dockerfile
  ok   A base python:3.11-slim
  ok   A set GALARDO_BIND=0.0.0.0
  ok   A EXPOSE 8090/8095/8899
  ok   A ada HEALTHCHECK
  ok   A healthcheck ke /api/v1/health
  ok   A CMD run_local
== B. compose ==
  ok   B ada docker-compose.yml
  ok   B ada services:
  ok   B port 8090/8095/8899
  ok   B volume data
  ok   B GALARDO_BIND di environment
  ok   B restart policy
== C. dockerignore ==
  ok   C ada .dockerignore
  ok   C mengabaikan .git
  ok   C mengabaikan .out
  ok   C mengabaikan backups
  ok   C mengabaikan __pycache__
== D. dukungan bind di kode ==
  ok   D ada modul yang menghormati GALARDO_BIND
  ok   D default tetap 127.0.0.1
== E. NATS ==
  ok   E service nats ada
  ok   E image nats
  ok   E GALARDO_NATS_URL di env
  ok   E depends_on nats
  ok   E modul bus ada
  ok   E bus fail-open (tanpa env -> skipped)
== F. OTLP ==
  ok   F service otel ada
  ok   F image collector
  ok   F GALARDO_OTLP_URL di env
  ok   F depends_on otel
  ok   F modul otlp ada
  ok   F otlp fail-open
  ok   F konfig collector ada
  ok   F konfig punya receiver otlp
== G. Postgres ==
  ok   G service pg ada
  ok   G image postgres
  ok   G GALARDO_PG_DSN di env
  ok   G depends_on pg
  ok   G volume pgdata
  ok   G modul pg ada
  ok   G pg fail-open

RESULTS: 41 passed, 0 failed
---
stopped (or not running)
```

---

## Bagian 2 - lapisan API (prefix /api/v1) + jalur Docker

Temuan F-18: probe 10-C memakai path tanpa prefix sehingga 404, padahal server
hidup. smoke.sh hanya menguji import, tidak menyentuh HTTP.

```
### tanpa token (harus 401/403, bukan 404)
GET /api/v1/health         -> 200
GET /api/v1/me             -> 200
GET /api/v1/version        -> 404
GET /api/v1/sources        -> 200
### dengan token
GET /api/v1/health         -> 200
GET /api/v1/me             -> 200
GET /api/v1/version        -> 404
GET /api/v1/sources        -> 200
### isi /health + /me
{"status": "ok", "service": "galardo-api", "version": "1.0", "time": "2026-10-17T15:18:45.632Z", "local_dev_override": false}
{"actor": "usr-operator", "user": {"id": "usr-operator", "email": "operator@lab.local", "role": "TEST_OPERATOR", "status": "ACTIVE", "org_id": "org-lab", "mfa_enabled": false}}
### 404 nyata (rute tak ada)
GET /api/v1/tidak-ada -> 404
NAME            IMAGE                                          COMMAND                  SERVICE   CREATED          STATUS                        PORTS
galardo-local   galardo:local                                  "python3 backend/run…"   galardo   6 seconds ago    Restarting (1) 1 second ago   
galardo-nats    nats:2.10-alpine                               "docker-entrypoint.s…"   nats      7 seconds ago    Up 6 seconds                  0.0.0.0:4222->4222/tcp, [::]:4222->4222/tcp, 0.0.0.0:8222->8222/tcp, [::]:8222->8222/tcp, 6222/tcp
galardo-otel    otel/opentelemetry-collector-contrib:0.104.0   "/otelcol-contrib --…"   otel      7 seconds ago    Up 6 seconds                  4317/tcp, 55678-55679/tcp, 0.0.0.0:4318->4318/tcp, [::]:4318->4318/tcp
galardo-pg      postgres:16-alpine                             "docker-entrypoint.s…"   pg        16 minutes ago   Up 13 minutes (healthy)       0.0.0.0:5433->5432/tcp, [::]:5433->5432/tcp
docker GET /api/v1/health     -> 200
docker GET /api/v1/me         -> 200
galardo-local  |     main()
galardo-local  |   File "/app/backend/run_local.py", line 86, in main
galardo-local  |     import api
galardo-local  |   File "/app/backend/api.py", line 23, in <module>
galardo-local  |     from scenario import parse_scenario_yaml, save_scenario_version, ScenarioError
galardo-local  |   File "/app/backend/scenario.py", line 14, in <module>
galardo-local  |     import yaml
galardo-local  | ModuleNotFoundError: No module named 'yaml'
stopped (or not running)
```

---

## Bagian 3 - Docker jujur + temuan F-19

F-19 (P0): container galardo crash-loop - image tanpa PyYAML:
    ModuleNotFoundError: No module named 'yaml' (backend/scenario.py:14)
Konsekuensi: bukti 'docker GET /health -> 200' di STEP-67 kemungkinan besar
berasal dari server HOST yang masih hidup di port 8090, bukan dari container.
Probe sekarang dilakukan setelah host dimatikan + pakai docker inspect.

```
NAME            IMAGE                                          COMMAND                  SERVICE   CREATED          STATUS                        PORTS
galardo-local   galardo:local                                  "python3 backend/run…"   galardo   11 seconds ago   Restarting (1) 1 second ago   
galardo-nats    nats:2.10-alpine                               "docker-entrypoint.s…"   nats      11 seconds ago   Up 10 seconds                 0.0.0.0:4222->4222/tcp, [::]:4222->4222/tcp, 0.0.0.0:8222->8222/tcp, [::]:8222->8222/tcp, 6222/tcp
galardo-otel    otel/opentelemetry-collector-contrib:0.104.0   "/otelcol-contrib --…"   otel      11 seconds ago   Up 10 seconds                 4317/tcp, 55678-55679/tcp, 0.0.0.0:4318->4318/tcp, [::]:4318->4318/tcp
galardo-pg      postgres:16-alpine                             "docker-entrypoint.s…"   pg        11 seconds ago   Up 10 seconds (healthy)       0.0.0.0:5433->5432/tcp, [::]:5433->5432/tcp
### health container (via docker inspect, bukan host)
restarting health=unhealthy
### probe HTTP dari host (kini hanya container yang mendengarkan)
GET /api/v1/health     -> 000
GET /api/v1/me         -> 000
### exec di dalam container (import yaml?)
Error response from daemon: Container 73f0275e8918c1c964d4121ffb2d22f973035dd2b4d22da8f77e8999b81dd3c9 is restarting, wait until the container is running
### log container (20 baris)
galardo-local  | Traceback (most recent call last):
galardo-local  |   File "/app/backend/run_local.py", line 102, in <module>
galardo-local  |     main()
galardo-local  |   File "/app/backend/run_local.py", line 86, in main
galardo-local  |     import api
galardo-local  |   File "/app/backend/api.py", line 23, in <module>
galardo-local  |     from scenario import parse_scenario_yaml, save_scenario_version, ScenarioError
galardo-local  |   File "/app/backend/scenario.py", line 14, in <module>
galardo-local  |     import yaml
galardo-local  | ModuleNotFoundError: No module named 'yaml'
galardo-local  | Traceback (most recent call last):
galardo-local  |   File "/app/backend/run_local.py", line 102, in <module>
galardo-local  |     main()
galardo-local  |   File "/app/backend/run_local.py", line 86, in main
galardo-local  |     import api
galardo-local  |   File "/app/backend/api.py", line 23, in <module>
galardo-local  |     from scenario import parse_scenario_yaml, save_scenario_version, ScenarioError
galardo-local  |   File "/app/backend/scenario.py", line 14, in <module>
galardo-local  |     import yaml
galardo-local  | ModuleNotFoundError: No module named 'yaml'
```

---

## Bagian 4 - F-19 diperbaiki: image memasang dependensi

Akar F-19: Dockerfile TIDAK pernah menjalankan pip install, dan requirements.txt
tidak ada. Jadi image = python polos; yaml hanya modul pertama yang tersandung.
Perbaikan: requirements.txt dibuat dari hasil scan AST, Dockerfile memasangnya.
smoke.sh diperbaiki: uji HTTP dijalankan SEBELUM ringkasan dan ikut menentukan rc.

```
### ps
NAME            IMAGE                                          COMMAND                  SERVICE   CREATED          STATUS                    PORTS
galardo-local   galardo:local                                  "python3 backend/run…"   galardo   11 seconds ago   Up 10 seconds (healthy)   0.0.0.0:8090->8090/tcp, [::]:8090->8090/tcp, 0.0.0.0:8095->8095/tcp, [::]:8095->8095/tcp, 0.0.0.0:8899->8899/tcp, [::]:8899->8899/tcp
galardo-nats    nats:2.10-alpine                               "docker-entrypoint.s…"   nats      11 seconds ago   Up 10 seconds             0.0.0.0:4222->4222/tcp, [::]:4222->4222/tcp, 0.0.0.0:8222->8222/tcp, [::]:8222->8222/tcp, 6222/tcp
galardo-otel    otel/opentelemetry-collector-contrib:0.104.0   "/otelcol-contrib --…"   otel      11 seconds ago   Up 10 seconds             4317/tcp, 55678-55679/tcp, 0.0.0.0:4318->4318/tcp, [::]:4318->4318/tcp
galardo-pg      postgres:16-alpine                             "docker-entrypoint.s…"   pg        11 seconds ago   Up 10 seconds (healthy)   0.0.0.0:5433->5432/tcp, [::]:5433->5432/tcp
### inspect galardo-local
status=running health=healthy restarts=0
### exec: import yaml di dalam container
yaml OK 6.0.3
### probe HTTP (hanya container yang mendengarkan)
GET /api/v1/health     -> 000
GET /api/v1/me         -> 000
### log container (12 baris)
galardo-local  | [galardo-target] v2 on http://127.0.0.1:8095  (/healthz, /api/*, /control/*)
galardo-local  | [galardo-target] ceiling: workers=unlimited backlog=unlimited  (0 = unlimited)
galardo-local  | [run_local] lab target ready  -> http://127.0.0.1:8095
galardo-local  | ==============================================================
galardo-local  |   GALARDO dashboard : http://127.0.0.1:8090/
galardo-local  |   API base         : http://127.0.0.1:8090/api/v1
galardo-local  | ==============================================================
galardo-local  | [galardo-api] listening on http://127.0.0.1:8090  (dashboard: http://127.0.0.1:8090/)
```

---

## Bagian 5 - F-20: port publish mati karena bind loopback

Gejala: container healthy (healthcheck menembak 127.0.0.1 DI DALAM container),
tetapi dari host GET /api/v1/health -> 000. Log container:
    [galardo-api] listening on http://127.0.0.1:8090
padahal Dockerfile menyetel GALARDO_BIND=0.0.0.0 -> run_local.py mengabaikannya.
Perbaikan: run_local.py membaca GALARDO_BIND (default 127.0.0.1); compose 0.0.0.0.
Ini juga menjelaskan mengapa bukti 'health 200' STEP-67 berasal dari server host.

```
### banner container
galardo-local  | [run_local] lab target ready  -> http://127.0.0.1:8095
galardo-local  | ==============================================================
galardo-local  |   GALARDO dashboard : http://127.0.0.1:8090/
galardo-local  |   API base         : http://127.0.0.1:8090/api/v1
galardo-local  | ==============================================================
galardo-local  | [galardo-api] listening on http://127.0.0.1:8090  (dashboard: http://127.0.0.1:8090/)
### inspect
status=running health=healthy restarts=0
### probe dari HOST (target 200, sebelumnya 000)
GET /api/v1/health     -> 000
GET /api/v1/me         -> 000
### isi /api/v1/health dari container

### smoke.sh lawan container (host dimatikan)
  [v] step_load jalan
tools/smoke.sh: line 31: 40437 Terminated: 15          python3 -m http.server 18101 --directory /tmp > /dev/null 2>&1
  [v] SKIP GET /api/v1/health (server tidak mendengarkan)
== SMOKE OK ==
```

---

## Bagian 6 - F-20 akar sebenarnya: bind literal di serve()

Catatan jujur: patch sebelumnya NO-OP karena run_local.py hanya memakai
GALARDO_BIND di port_free(), bukan saat bind. Socket benar-benar diikat di
api.serve() dan lab_target.serve() dengan literal 127.0.0.1.
Perbaikan: helper _bind_host() (GALARDO_BIND, default 127.0.0.1) dipakai di
kedua serve() + banner.

```
### banner container
galardo-local  | SyntaxError: f-string: unmatched '('
galardo-local  |   File "/app/backend/run_local.py", line 83
galardo-local  |     os.environ["GALARDO_TARGET_ORIGIN"] = f"http://{os.environ.get("GALARDO_BIND", "127.0.0.1")}:{target_port}"
galardo-local  |                                                                     ^^^^^^^^^^^^
galardo-local  | SyntaxError: f-string: unmatched '('
### inspect
status=restarting health=unhealthy restarts=10
### probe dari HOST (target 200)
GET /api/v1/health     -> 000
GET /api/v1/me         -> 000
### isi /api/v1/health

### smoke.sh lawan container (host mati) - harus [v] 200
== SMOKE: step_load benar-benar jalan ==
  [v] step_load jalan
tools/smoke.sh: line 31: 41047 Terminated: 15          python3 -m http.server 18101 --directory /tmp > /dev/null 2>&1
  [v] SKIP GET /api/v1/health (server tidak mendengarkan)
== SMOKE OK ==
```

---

## Bagian 7 - F-21: f-string bersarang butuh Python 3.12

Patch banner memakai f"...{os.environ.get("GALARDO_BIND", "127.0.0.1")}..."
yang hanya legal di 3.12+. Host & image 3.11 -> SyntaxError -> container
crash-loop (restarts=10) dan jalur host juga mati. Perbaikan: kutip tunggal
di dalam ekspresi f-string.

```
### banner container
galardo-local  |   GALARDO dashboard : http://0.0.0.0:8090/
galardo-local  |   API base         : http://0.0.0.0:8090/api/v1
galardo-local  | ==============================================================
galardo-local  | [galardo-api] listening on http://0.0.0.0:8090  (dashboard: http://0.0.0.0:8090/)
### inspect
status=running health=healthy restarts=0
### probe dari HOST (target 200)
GET /api/v1/health     -> 200
GET /api/v1/me         -> 200
### isi /api/v1/health
{"status": "ok", "service": "galardo-api", "version": "1.0", "time": "2026-10-17T15:28:04.522Z", "local_dev_override": false}
### smoke.sh lawan container (host mati)
  [v] step_load jalan
tools/smoke.sh: line 31: 41535 Terminated: 15          python3 -m http.server 18101 --directory /tmp > /dev/null 2>&1
  [v] GET /api/v1/health -> 200
== SMOKE OK ==
```

---

## Kesimpulan (item 10)

Jalur lokal - bukti mentah:
- demo verdict `state=RECOVERED down_verified=True ttr=43.864 transisi=4`, transisi
  UP->SUSPECT->DOWN->RECOVERING->RECOVERED, `peak_waiting=288 saturated=True`  (GOAL: DOWN)
- override `404 status=404 forced=True` dan `blank status=200 body_len=0 forced=True` (GOAL: 404 & BLANK)
- crypto 52/0, trust 39/0 (termasuk E2E lewat TCP), own1 26/0, capacity plafon 4987 rps
  (knee 100 VU), backup 14/0, docker-verify 41/0  -> nol FAIL

Jalur Docker - bukti mentah:
- `status=running health=healthy restarts=0`, banner `listening on http://0.0.0.0:8090`
- dari HOST: `/api/v1/health -> 200`, `/api/v1/me -> 200`, `smoke.sh [v] ... 200` tanpa server host
- isi /api/v1/health: {"status": "ok", "service": "galardo-api", "version": "1.0", ...}

Temuan yang lahir DAN ditutup di step ini: F-18 (prefix probe + smoke tanpa HTTP),
F-19 (image tanpa dependensi), F-20 (bind loopback mematikan port publish),
F-21 (f-string bersarang butuh py3.12). Koreksi bukti STEP-67 ditulis di HASIL-67.

Status: item 10 TUNTAS. Sisa backlog: temuan terbuka P0.1b, F-7, F-4, F-3.
