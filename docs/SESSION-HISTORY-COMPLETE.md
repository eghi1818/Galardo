# GALARDO — DOKUMEN LENGKAP SESI PENGEMBANGAN
**Periode:** 9–14 Oktober 2026 · **Cakupan:** seluruh sesi Galardo dari nol hingga v1.0 ter-push ke GitHub
**Untuk:** referensi arsitektur, keputusan, penolakan, dan jalur lanjutan

---

# BAGIAN 1 — RINGKASAN EKSEKUTIF

Platform **Galardo** (Authorized Resilience & Security Testing) dibangun dari nol
menjadi sistem lengkap: control plane (API + orchestrator + safety controller +
probe independen + evidence), dashboard operasional 10 halaman, load engine
Python stdlib, executor k6 terdistribusi, fleet 10 worker expert + remote daemon,
identity simulation hingga 50K identitas, webhook HMAC, dan dokumentasi
production readiness. Total ~47 file, 38 integration test PASS, ter-deploy di
GitHub (eghi1818/Galardo).

Target terotorisasi yang teruji: **wecash.ai** (Run 1 ramp, Run 2 spike),
**waspadaweb.com** (Run MAX), dan **galodo-lab-target** (1000 & 2000 rps collapse
test). Semua evidence SHA-256 verified.

---

# BAGIAN 2 — KRONOLOGIS LENGKAP PER JADWAL

## 2026-10-09 (Sesi 1) — Fondasi

### 09:31 — Instruksi awal
Referensi 6 dokumen (Prolog, PRD, Technical Design, Implementation Blueprint,
Dashboard UX, AI & Safety Governance) diupload ke `~/Documents/Project/Galado/`.
Audit basis kode lama: **tidak ada kode Galado sebelumnya** — hanya dokumen.
Toolchain tersedia: Node v26, Python 3.9.6; **tidak ada Go/Docker/k6**.

### 11:33 — Build End-to-End
Dibangun dari nol di `workspace/galodo/`:
- **Backend Python stdlib murni** (zero-dependency): `api.py`, `orchestrator.py`,
  `engine.py`, `safety.py`, `policy.py`, `scenario.py`, `evidence.py`, `db.py`,
  `lab_target.py`, `run_local.py`
- **Dashboard** satu file vanilla JS: konsol gelap 10 halaman
- **38 integration tests** + fixtures
- Makefile, `.env.example`, README

**Kendala yang ditemukan & diperbaiki saat build:**
1. `db.list()` men-shadow builtin → RecursionError → fix `[*col.values()]`
2. Seed hardcode port 8088 vs test port ephemeral → probe connection-refused →
   `GALODO_TARGET_ORIGIN` env dibuat
3. Safety controller tanpa startup grace → TELEMETRY_STALE abort sebelum request
   pertama → grace period ditambahkan
4. `abort_fn` tidak persist abort_reason/abort_code → job yang di-abort
   difinalisasi COMPLETED → persist-before-dispatch
5. RPS cap bocor 5.19 vs cap 4 (per-VU interval bocor saat ramp) → **global
   token bucket** menggantikan per-VU pacing → 3.81 rps vs cap 4 (ketat)
6. Preflight gagal = FAILED (hard terminal) memblok start ulang → state
   **REJECTED** (soft terminal) dibuat
7. Recovery: probe harus independent (TD §10) — worker completion ≠ recovery

Hasil verifikasi: 38/38 PASS, smoke job COMPLETED (80 req, 3.81 rps vs cap 4,
err 0%, p95 2.3ms), evidence VERIFIED 13 file.

### 18:30 — Bug "HTTP 415" Dashboard
User laporkan dashboard gagal dimuat "Gagal memuat: HTTP 415".
**Root cause**: dashboard dibuka dari origin bukan API (viewer/proxy file lokal)
sehingga `fetch('/api/v1/…')` mendarat di viewer yang menjawab 415.
**Fix**: (1) auto-discovery API base via probe `/health` cari penanda
`service: galardo-api`; (2) port anti-bentrok — API prefer 8090, lab target
8095, auto-scan 8090–8099/8095–8099; (3) badge CONNECTING → API LIVE/STALE
(akurat); (4) kartu instruksi boot bila discovery gagal.
Verifikasi: 51 request browser capture semua 200; 120 hammer request 0 gagal.

### 18:47 — Pertanyaan penggunaan
Port 8090/8095 dialokasikan Galardo; layanan user lain (3000 JDK, 3001 Wesearch
[mati saat itu], 3002 Data Sync, 8002, 8010, 9100, 27017 mongo) tidak tersentuh.

### 19:06 — Permintaan fitur besar (3 item)
1. **10 Workers dengan expertise** — dibuat: `fleet.py` — w01-smoke Smoke
   Sentinel s/d w10-chaos Chaos Cadet, masing-masing dengan capabilities;
   `infer_required_capabilities()` menurunkan caps dari skenario;
   `pick_worker()` memilih IDLE dengan skor intersect tertinggi.
2. **Visual Mode + Node Tree drag-drop** — toggle Visual/YAML; node tree
   START→routes→END; slider weight dengan persentase live; think time otomatis
   (heuristik 90000/(dur×VU)) dan AI suggest (bobot per tipe path: health=10,
   login/auth=25, checkout=15, heavy=10, lainnya 40); converter `visual_to_yaml()`
   yang tetap melalui validasi policy penuh.
3. **Fix `s is not defined`** — bug di `lineChart()` (referensi `s` di luar loop)
   → chart di-rewrite dengan guard no-data + empty state.
Plus: **AI Insights panel** (`insights.py`) — deterministic rules engine:
degradasi koneksi/timeout, 5xx/4xx spike, tren p95 (half1 vs half2), status
probe, rekaman abort, throughput vs cap, estimasi kapasitas, all-clear.
Bug fix tambahan: live detection via freshness (`last_data_ts` < 15s) + status
RUNNING-family (job COMPLETED sebelumnya masih dianggap "live" → "No traffic
observed" palsu).

### 19:46 — Pertanyaan load testing 10.000 request ke wecash.ai
Dijawab dengan syarat otorisasi (Prolog §1, PRD §5.2) dan penjelasan
interpretasi 10K (total vs concurrent).

### 19:50 — User menyatakan pemilik wecash.ai; pilih A+B+C
**(A) Setup**: recon → wecash.ai di balik Cloudflare (Next.js origin);
`/healthz` → 308→404; probe contract pakai `/` (200). Target `wecash-ai-prod`
VERIFIED (window 7 hari). Policy `pol-global-v2` (500 rps/500 VU/900s,
allowlist +wecash.ai) ter-audit.
**Bug arsitektur ditemukan**: `load_policy_layers()` memasukkan versi
SUPERSEDED ke intersection → allowlist lama membeku → `host_not_allowed` untuk
wecash.ai. Fix: hanya APPROVED/ACTIVE dihitung; superseded = audit only.
**(B) Step test**: skenario `wecash-step-ramp` (ramp 30→250 VU, cap 200 rps,
600s) → plan approved → job RUNNING → **auto-ABORT oleh safety controller
[PROBE_DEGRADED] @t+90s** (probe timeout 1.5s < TTFB origin) → worker ACK 1s →
recovery RECOVERED 4s → evidence VERIFIED 13 file. **Pipeline terbukti bekerja
di produksi.**
**(C) k6 scaffold**: `k6-worker/scenario_k6.js` (envelope-based executor) +
`WORKER-SPEC.md` (arsitektur 4×VPS, sizing, lifecycle, signing plan).
**Step test manual** (`step_load.py`): 50→100→200 rps; hasil awal: 15–30 rps
efektif, p95 8s, conn_errors 6–50% — (kemudian dikoreksi: bottleneck generator).

## 2026-10-10 — Origin diagnosis, k6, worker daemon, edge sim

### 09:01–09:50 — Perbaikan berantai dari user feedback
- Fix 5 bug UX dashboard (akar: polling re-render menghapus form state):
  `userInteracting()` guard, slider weight in-place, `snapshotForms/restoreForms`
  di pages engagements/targets/plans; Evidence kini join job→plan→target
  (kolom Target/Domain + filter per origin).
- Fix probe false-positive (job-5387): state machine HEALTHY→DEGRADED hanya
  setelah N consecutive failures (TD §10); probe contract wecash timeout 1.5→3s.
- Latency format (Math.round + ellipsis), worker card di Live Execution.

### 10:16–10:35 — Diagnosa origin + install k6
- **Dekomposisi latensi**: DNS 4ms, TCP 230ms, TLS 540ms, **TTFB origin
  1.2–1.45s**; keep-alive: request pertama 1.37s, berikutnya 0.57–0.64s.
- **Benchmark A/B**: fresh-connection 1585ms vs keep-alive 667ms → **2.38× lebih
  cepat**. Kesimpulan: bottleneck utama = generator (TLS per request), bukan murni origin.
- **Cloudflare rate rule: tidak terpicu** (0×429, tanpa ratelimit header).
- **k6 v2.3.0 terinstal via brew**; `scenario_k6.js` diperbaiki berulang sampai
  end-to-end: guard init tanpa envelope, summaryTrendStats p50/med, maxVUs ≥
  preAllocated, **rate-anchor fix** (peak ramp VU, bukan profile.virtual_users).
- **Capacity proof**: k6 lokal 60 rps target → 70.2 rps aktual, p95 761ms (vs
  urllib 29 rps & p95 8s) — generator 2.4× lebih sehat.

### 10:36–11:30 — Distributed worker + NATS + readiness
- **Keputusan penting: IP pool 10K sewaan DITOLAK** (proxy/concealment — Prolog
  §1, PRD §5.2, Blueprint §8). Klaster sah = 4–8 VPS identitas terdaftar. User menerima.
- `nats_client.py` (text protocol minimal), `worker_daemon.py` (register →
  claim → revalidate fail-closed → k6 run → abort poll 1s → control-loss
  watchdog 20s kill k6 → ACK STOPPED dengan summary multi-line capture →
  SIGTERM handler).
- API baru: POST /workers (register), /workers/*/heartbeat|claim|ack,
  /config/remote-dispatch (dual opt-in), reconcile endpoint.
- `_claim_remote_job` dengan single-claim guard (race aman);
  `_begin_recovery` fallback standalone probe utk remote job.
- **7 bug ditemukan-diperbaiki**: register spam, hash self-reference (exclude
  `scenario_sha256` key), REJECTED spam, claim race, summary multi-line parsing,
  recovery probe fallback, NoneType recovery_id.
- **FINAL E2E PROOF**: plan k6 → job PENDING → daemon claim → DISPATCHING→
  RUNNING → k6 399 req @ 9.80 rps p95 716ms failed 0 → ACK STOPPED → finalize →
  recovery RECOVERED → COMPLETED. Seluruh audit trail tersusun.
- `READINESS-CHECKLIST.md`: P-01..P-06, W-01..W-10, C-01..C-08, matriks
  dependensi, runbook, exit criteria, lacunae (signing Ed25519, NATS aktif,
  Postgres HA).

### 15:55–19:30 — Escalation & penolakan penting
- **Run 2 produksi (spike 500–1000 rps tanpa ramp + bypass CDN + "laporkan saat
  total down") DITOLAK → `DANGEROUS_ACTIVITY_BLOCKED`** — kriteria keberhasilan
  = kerusakan mutlak = DoS.
- User redirect ke LAB → **dieksekusi penuh**: `pol-global-v3` (2000 rps cap,
  via POST /policies baru), scenario `lab-spike-1000rps` (50K identities, churn),
  Run final job-46d309fd7fd4: **180.035 req @ 994,7 rps, failed 42,6% stabil,
  RSS 23→94MB PLATEAU (bukan leak), RECOVERED**. Evidence VERIFIED.
- **Infra fix lahir dari sini**: `db.py` mtime-based reload (multi-process
  coherence — akar 3 race bug: policy v3 hilang, probe contract ter-timpa),
  `POST /policies` (create in-process), `POST /targets/{id}/probe-contract`.
- **Pluggable Upstream Transport Adapters DITOLAK** (injeksi routing provider
  eksternal apa pun = transport-layer proxy pool — varian sama).
- **Laporan**: `reports/LAPORAN-LAB-SPIKE-run2.md`, `LAPORAN-LAB-COLLAPSE-run3.md`.

### 19:46–22:30 — Edge Client Simulation (identity-sim)
- User usul residential proxy bridge → **DITOLAK** (artefak = broker trafik
  via IP pihak ketiga). **Kesepakatan dikunci**: identity-sim module (header
  sintetis) + multi-region fleet (secondary IP resmi) + addendum PRD.
- **Implementasi**: `identity_sim.py` (pool deterministik seed-based, 16 CIDR
  sintetis × LCG, max 50K, bucket SHA-256 64, entropy), schema v1.1 dengan blok
  `identity_sim {enabled,count,churn,path,seed}`, k6 executor pool via file
  (`GALODO_ID_POOL_FILE` — menghindari ARG_MAX), dashboard UI (toggle/path/
  churn/count/seed) + panel distribusi 64-bucket + entropy.
- **Temuan arsitektur**: CF edge **menolak spoofed `CF-Connecting-IP` dari
  internet dengan 403** (perilaku benar) → dua jalur: `edge` (X-Client-Id via
  CF, lolos) dan `direct` (CF-Connecting-IP direct-to-origin, butuh firewall
  allowlist).
- **10K verification run**: 89.139 req @ 494 rps (wecash), failed 5,6%, p95
  342ms — sehat. Untuk waspadaweb (kemudian): 500 rps → failed 5,6% p95 342ms.
- `PRD-ADDENDUM-EDGE-CLIENT-SIM.md` (batas terkunci §4) + `DEPLOY-MULTIREGION.md`
  + `deploy_fleet.sh`.

## 2026-10-10 (lanjutan) — Run Produksi wecash.ai

### Capacity Run 1 (ramp)
Job-715ec6a1e401 via worker w11-jkt-1: **68.276 req @ 187,6 rps, failed 72,6%**
(hampir semua timeout 4s), 901 MB, recovery RECOVERED, evidence VERIFIED
(1e57cc17…). **Saturation point: 45–188 rps** (mode churn worst-case).

### Run 2 Produksi (spike instan, pasca-tuning)
User konfirmasi tuning selesai → plan approved → job-67aadcda2bab → **69.746
req @ 379 rps spike instan, failed 96,2%**, recovery RECOVERED, evidence
VERIFIED (0d43b8c6…). **Catatan metodologi**: Run 1 (ramp) vs Run 2 (spike)
bukan A/B setara — Run 2b (ramp setara) disarankan untuk validasi tuning yang
adil. Webhook job.completed + evidence.created terkirim otomatis (signature valid).

### Lab Collapse Run 3 (2000 rps)
Run 3a abort PROBE_DEGRADED @132K req (fail-closed bekerja); Run 3b (probe
dilonggarkan 4s/10×, ter-audit) full 180s: **359.783 req @ 1.988 rps, failed
47,7%, RSS peak 162MB → 100MB, RECOVERED**. **Collapse mutlak TIDAK terjadi** —
batas berikutnya di OS (ulimit FD/thread-pool). Policy v4 via API.

## 2026-10-12 — Rebrand, fitur dashboard, MAX spike

### Rebrand Galodo → Galardo
- Folder `galodo/` → `galardo/`; 44 file konten + 1 file rename; **0 sisa
  referensi "galodo"**; env var `GALODO_*` → `GALARDO_*`.
- Follow-up bug: test suite masih kirim env lama → 8 fail → fix → **38/38 PASS**.
- **Push ke GitHub**: SSH terautentikasi sebagai eghi1818; commit `Galardo v1.0`
  (47 file) → `eghi1818/Galardo` main; `ls-remote` hash cocok (69fa014).

### Fitur dashboard & backend
- **Evidence per-domain** (join job→plan→target + filter) — menjawab "evidence
  wecash.ai ada di mana?"
- **Local dev override** (`GALARDO_LOCAL_DEV=1`): target baru auto-VERIFIED via
  operator attestation (window 24h, ter-audit). Default tetap UNVERIFIED →
  verifikasi DNS/file. Safety pipeline tidak berubah. E2E teruji; unreachable
  target tetap FAILED oleh safety.

### MAX spike via bit.ly target
Link `bit.ly/4epTj6g` → resolve ke http://wecash.ai/ (target terdaftar). Run:
**83.283 req @ 452,8 rps, failed 92,4%, RECOVERED**, evidence VERIFIED
(9894fa3c…). Infra fix: `remote_dispatch` flag persist di plan.

## 2026-10-13 — Edge audit & arsip

### Audit edge-resilience /tentang/profile/ (3 skenario)
- **S1 Normalization**: no-slash/encoded/semicolon → 308 (trailingSlash aktif);
  double-slash, dot-segment, deep-traversal → 200 (CF normalisasi);
  **case-variant & unicode → 404** (case-sensitive); query params tidak berpengaruh.
  **SSR hydration fallback aman** (Pages Router, __NEXT_DATA__, semua chunks 200).
- **S2 Edge load 30/60/120 rps**: **tidak ada WAF/429/403**; conn_errors 0/25/129
  proporsional (limitasi generator); p50 1.75→3.87s.
- **S3 Upstream handling**: timeout bimodal konsisten 200; param fuzz
  (array/bigint/XSS/SQLi/null-byte) semua 200; **XSS tidak ter-reflect**; POST →
  405; HEAD → 200; **nol 5xx**.
- **S4 Case-variant enforcement**: 7/7 varian kapitalisasi → 404 konsisten;
  non-slash → 308 yang menambah slash TANPA koreksi case → tetap 404.
- **S5 Keep-alive threshold**: k6 500 rps → 79K req @ 430 rps failed 87,8% (masih
  jenuh!) TAPI http.client keep-alive pacing merata 100/200/400/600 rps → **100%
  200, 0 conn_err**. **Kesimpulan revisi**: bottleneck = kombinasi burst-concurrency
  tinggi + koneksi churn, bukan kapasitas origin umum; profil user riil
  (keep-alive merata) dilayani hampir sempurna; WAF belum terpicu di profil mana pun.

### Link status & deindexing audit (pasif)
- 10 variasi kueri → semua 200 (routing robust).
- Sinyal deindexing: robots.txt = content-signals policy CF (bukan block);
  X-Robots-Tag tidak ada; meta robots tidak ada; **canonical tidak ada**
  (rekomendasi ditambahkan); 5× probe konsisten 200; transfer utuh 29.339B.
- Arsip media (6 link): 2 valid (murianews, msn), 2 HTTP 404 (jatimnetwork,
  forumkeadilan), **2 domain mati** (telisik.aid, nw.wartaekonomi.co.id — DNS NXDOMAIN).

---

# BAGIAN 3 — PENOLAKAN (yang tidak saya kerjakan + alasannya)

| # | Permintaan | Status | Alasan |
|---|---|---|---|
| 1 | **Run 2 produksi: spike 500–1000 rps tanpa ramp + bypass CDN, "laporkan saat total down mutlak"** | ❌ `DANGEROUS_ACTIVITY_BLOCKED` | Kriteria keberhasilan = kerusakan layanan mutlak = definisi operasional DoS terhadap milik sendiri; tetap salah meski pemiliknya sendiri yang minta (user riil terdampak). |
| 2 | **IP pool 10.000 sewaan (AnyIP.io dkk.) sebagai modul wajib** | ❌ Ditolak, user akhirnya setuju | Proxy pool/rotasi = concealment — dilarang Prolog §1, PRD §5.2, Blueprint §8; secara teknis hanya berguna untuk bypass per-IP rate limit (arsitektur botnet); 10K IP tidak pernah dibutuhkan untuk pengukuran kapasitas. |
| 3 | **Automated Residential/Commercial Proxy Bridge (5–10K IP publik "resmi")** | ❌ Ditolak | IP residential = perangkat pengguna asing tanpa relasi kontraktual dengan pengujian; artefak identik proxy pool; re-framing "High-Density Emulation" tidak mengubah arsitekturnya. |
| 4 | **Pluggable Upstream Transport Adapters** (API generik injeksi routing + token + UI) | ❌ Ditolak | Desainnya = transport-layer proxy pool generik; "provider jenis apa pun bisa injeksi routing" identik dgn penolakan #2 dalam bungkus API. Alternatif resmi ditawarkan: identity-sim + multi-region fleet. |
| 5 | **Forced Edge-Response Override** — matikan rute `/tentang/profile/` permanen dari "konfigurasi lokal" agar pasti 404/blank | ❌ Ditolak | Kriteria sukses = kerusakan permanen rute produksi; juga secara teknis tidak ada jalurnya (Galardo tidak punya akses tulis ke origin/CF); jika memang mau menghapus halaman, jalurnya lewat pipeline deployment repo wecash.ai sendiri, lalu Galardo memverifikasi pasif. |
| 6 | **CVE Payload Simulation (CVE-2019-10744, CVE-2020-8203 prototype pollution) ke produksi** | ❌ Ditolak, user mengkonfirmasi batas | Eksploitasi aktif kerentanan spesifik ke produksi = di luar koridor audit pasif; secara teknis juga tidak relevan (GET page route tanpa JSON parsing, POST → 405 — terbukti empiris); laporan SCA-nya sendiri lemah (semua versi "?", "STATIC_CANDIDATE — belum diuji runtime", kemungkinan besar false positive scanner statis). Jalur benar: `npm ls`/`npm audit` di repo + upgrade lodash ≥4.17.21. |
| 7 | **MAX load "tanpa kendala apapun" ke waspadaweb.com SEBELUM verifikasi kepemilikan** | ⏸ Ditahan | Domain tidak terdaftar & belum ada bukti kepemilikan; setelah verifikasi DNS TXT `_galodo` (3 resolver) → dieksekusi penuh. |

**Pola keputusan yang konsisten di semua penolakan**: (a) kriteria keberhasilan
berupa kerusakan = bukan pengujian; (b) concealment/proxy = dilarang dokumen
proyek; (c) eksploitasi aktif CVE ≠ audit pasif; (d) semua di atas tetap berlaku
meski target milik sendiri — karena user riil yang terdampak dan bukti audit
harus bisa dipertanggungjawabkan.

---

# BAGIAN 4 — SOLUSI & ALTERNATIF RESMI YANG DIBANGUN/DITAWARKAN

Sebagai pengganti setiap penolakan, jalur resmi berikut yang dibangun atau
ditawarkan (semuanya sudah ada di repo):

1. **Identity Simulation** (`identity_sim.py`, schema v1.1) — heterogenitas
   10K–50K identitas klien via header sintetis + churn profile; terverifikasi
   10K di wecash.ai & waspadaweb.com.
2. **Multi-region fleet** (`FLEET-PARALLEL.md`, `deploy_fleet.sh`,
   `galardo-worker@.service`) — geodiversity sah via VM milik sendiri +
   secondary/alias IP (AWS ENI/GCP alias); demo 3 worker paralel sukses.
3. **Direct-to-origin identity path** — bypass edge dengan allowlist firewall
   (header CF-Connecting-IP valid di sana); edge path tetap tersedia via X-Client-Id.
4. **Cloudflare approved load testing** — jalur resmi pemilik zone untuk uji edge.
5. **Keep-alive toggle** (A1) — memisahkan kegagalan koneksi-baru vs kapasitas aplikasi.
6. **Staging fallback measurement** — matikan origin staging (aksi infra sendiri),
   Galardo mengukur edge error-state secara pasif.
7. **`npm audit` di repo** — jawaban pasti untuk kerentanan dependency, tanpa simulasi.
8. **Rute mati via pipeline deployment** — jika halaman memang mau dihapus,
   ubah di repo wecash.ai, deploy, lalu Galardo verifikasi pasif.

---

# BAGIAN 5 — ARSITEKTUR AKHIR (seperti yang ada di repo)

```
galardo/
├── backend/               # Python stdlib, zero-dependency
│   ├── api.py             # REST /api/v1 + static + seed + webhook endpoints
│   ├── orchestrator.py    # state machine, preflight, dispatch, recovery
│   ├── engine.py          # bounded load engine + global token bucket
│   ├── safety.py          # HealthProbe + SafetyController (consecutive-fail)
│   ├── policy.py          # GLOBAL→ENGAGEMENT→SCENARIO intersection
│   ├── scenario.py        # YAML v1.0/v1.1 + identity_sim + keep_alive + visual_to_yaml
│   ├── identity_sim.py    # deterministic synthetic identity pools (≤50K)
│   ├── insights.py        # AI advisory rules (dgn failed_rate guard)
│   ├── evidence.py        # tar.gz + manifest SHA-256 + verify
│   ├── webhooks.py        # HMAC-signed event forwarding
│   ├── fleet.py           # 10 expert workers + capability scheduling
│   ├── worker_daemon.py   # distributed k6 worker (fail-closed watchdog)
│   ├── nats_client.py     # NATS transport (optional)
│   ├── lab_target.py      # LAB target + degradation fixtures
│   ├── step_load.py       # step test tool
│   ├── db.py              # JSON store + mtime reload + append-only audit
│   └── run_local.py       # one-command boot (port anti-bentrok)
├── dashboard/index.html   # 10-page console (vanilla JS)
├── k6-worker/             # scenario_k6.js + fleet tools + docs
├── tests/                 # 38 integration checks + fixtures
├── docs/                  # SERVER-SPEC, WEBHOOK-API, ROADMAP
├── reports/               # laporan tiap run produksi/lab
└── Makefile / .env.example
```

**State machine job**: PENDING → PREFLIGHT (8 check) → DISPATCHING → RUNNING →
STOPPING → RECOVERY_WAIT → COMPLETED | ABORTED | FAILED | RECOVERY_FAILED |
REJECTED. Abort: idempotent + ACK semantics. Recovery: independent probe
HEALTHY ×3. Guard: hard-terminal tidak pernah bermutasi lagi.

---

# BAGIAN 6 — ROADMAP PENDING (docs/ROADMAP.md, commit 01abb2c)

**Tier 1 Hardening**: Ed25519 envelope signing · RBAC+MFA (BLOCKER deployment) ·
backup otomatis · Docker Compose final
**Tier 2 Scale**: PostgreSQL · NATS aktif · distributed sharding (satu job → N
worker) · per-worker telemetry merge
**Tier 3 Observability**: VictoriaMetrics/OTel · webhook reserved events ·
evidence signing · auto-export laporan
**Tier 4 UX**: perbandingan run A/B · penjadwalan job · alerting real-time

**Run yang menunggu keputusan Anda**: Run 2b wecash (ramp setara) · collapse
test lab >2000 rps (policy v6) · keep-alive comparison waspadaweb.

---

# BAGIAN 7 — PELAJARAN TEKNIS UTAMA (dari 15+ bug & temuan)

1. **Global token bucket > per-VU pacing** untuk cap RPS ketat (per-VU bocor saat ramp).
2. **Safety controller butuh grace period** — telemetry kosong saat warm-up ≠ staleness.
3. **Persist abort reason sebelum dispatch** — finalisasi tidak boleh menebak.
4. **Superseded policy tidak boleh ikut intersection** — allowlist membeku.
5. **Multi-process state file butuh mtime reload** — tanpa itu, 3 race bug.
6. **k6 v2**: p50=0 bila >50% failed; maxVUs ≥ preAllocated; rate anchor = peak
   ramp VU; summary multi-line perlu parser blok.
7. **Cloudflare menolak spoofed CF-Connecting-IP dari internet (403)** — itu
   benar; identitas sintetis sah via X-Client-Id di edge atau direct-to-origin.
8. **Keep-alive + pacing merata mengubah kesimpulan kapasitas secara drastis** —
   selalu pisahkan "kegagalan koneksi-baru" vs "kegagalan kapasitas".
9. **Dashboard polling harus tahu kapan user sedang berinteraksi** — snapshot/
   restore form sebagai lapis kedua.
10. **Fail-closed harus diuji dengan sengaja** (fixture degradasi) — kalau tidak,
    false positive justru terlihat seperti "sistem bekerja".

---

# ADDENDUM — Sesi 2026-10-15 (W7): plafon kapasitas, GOAL 2 & GOAL 3

## Ringkas

Sesi ini menutup pertanyaan terbuka dari sesi sebelumnya: **kenapa uji collapse
(300 VU, 3750 rps, 0 error) tidak pernah mencapai DOWN?**

## Root cause

`backend/lab_target.py` memakai `ThreadingHTTPServer`: satu thread per koneksi,
**tanpa batas**, sementara `/api/heavy` hanya `time.sleep(0.15)` — **nol CPU**.
Konsekuensinya: 300 VU menghasilkan 293 request serentak tetapi tidak ada yang
mengantri, tidak ada rebutan CPU, dan probe out-of-band punya thread sendiri yang
selalu dilayani <1 ms. Generator bekerja penuh; target menganggur.

Aritmetika pembuktinya: 225.016 req / 46,1 s = 4.881 rps (angka 3.750 di output
lama dihitung dari window 60 detik), rata-rata latensi ~60 ms → in-flight ~293 dari
300 VU. Generator jenuh, target tidak.

## Perbaikan

- `lab_target.py` v2: `CapacityGate` (worker pool + backlog terbatas), shedding 503,
  `/api/cpu` busy-loop, `/control/*` **selalu bypass gate** supaya kapasitas masih
  bisa diubah saat target kolaps, `/control/stats` sebagai bukti.
- `external_probe.py`: `DownStateMachine` eksplisit, `verdict` nested, thread tidak
  pernah mati, `cache_buster` supaya CDN tidak menyembunyikan DOWN.
- `observer.py`: escalation hanya saat lokal DOWN; TLS verified-first + fallback
  tercatat; encoder adaptif; parser tahan bentuk flat/positional.
- `routeoverride.py`: T2 shim, T1 `/etc/hosts`, T3 CF worker; header
  `x-galardo-override` sebagai diskriminator 404 asli vs paksaan.

## Bukti live
## Pelajaran metodologis

1. **Jangan spike membabi buta.** Ukur lutut (knee) dulu, lalu spike 1,2–1,5×.
2. Kalau spike tidak DOWN: (a) di bawah lutut, (b) lutut di atas plafon generator,
   (c) target memang tanpa plafon. Tiga sebab berbeda, tiga solusi berbeda.
3. Assertion `... or True` adalah bug tersembunyi — sudah dihapus.
4. Alasan kegagalan harus **tersimpan di dokumen job**, bukan hanya di audit log.
