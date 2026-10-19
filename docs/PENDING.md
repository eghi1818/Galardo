# PENDING & KONEKSI — Galardo

Daftar ini BUKAN backlog HANDOFF item 1-10 (yang sudah tuntas), melainkan sisa yang
memang belum ada. Tiap item wajib punya: Lokasi, Kebutuhan, Dampak bila absen,
Lanjutan (langkah konkret), Bukti yang akan dibuat, Estimasi, Prasyarat dari Anda.

Aturan kerja: satu item = satu STEP, pola tetap (baca jangkar -> patch -> verifier ->
make gate -> commit + docs/HASIL-<n>.md). Tidak ada klaim tanpa bukti.

## Ringkasan prioritas
| # | Item | Prioritas | Estimasi | Prasyarat |
|---|---|---|---|---|
| P1 | CI gate (GitHub Actions) | P1 | 1 blok | izin repo |
| P2 | Adapter provider proxy/residential | P1 | 1-2 blok | kredensial provider |
| P3 | subfinder/nikto di image Docker | P2 | 1 blok | - |
| P4 | Rate limit / WAF dasar | P2 | 1 blok | - |
| P5 | Pengerasan mode PG multi-proses | P3 | 1 blok | - |
| P6 | Nonce CSP (buang unsafe-inline) | P3 | 1 blok | - |

## Tabel koneksi eksternal (Galardo connect ke mana)
| Tujuan | Host:Port | Protokol | Diatur oleh | Wajib? | Status |
|---|---|---|---|---|---|
| PostgreSQL | host:5432 | TCP | `GALARDO_PG_DSN` | tidak | aktif di compose |
| NATS | host:4222 | TCP | `GALARDO_NATS_URL` | tidak | opt-in |
| OTLP collector | host:4318 | HTTP | `GALARDO_OTLP_URL` | tidak | opt-in |
| DNS resolver | 1.1.1.1 dll :53 | UDP | `DNS_CANDIDATES` | ya (fitur UDP/ownership) | aktif |
| NTP | host:123 | UDP | internal | tidak | aktif saat probe UDP |
| SSDP | 239.255.255.250:1900 | UDP | internal | tidak | aktif saat probe UDP |
| traceroute | ICMP/UDP | raw | `GALARDO_EXTTOOL_TIMEOUT` | tidak | biner lokal |
| Target yang diuji | 80/443 | HTTP(S) | `canonical_origin` per source | ya | ditentukan Anda |
| Cloudflare API | api.cloudflare.com:443 | HTTPS | `GALARDO_CF_TOKEN` (+zona) | tidak | kredensial BELUM diisi |
| Provider proxy/residential | mis. api.anyip.io:443 | HTTPS | BELUM ADA | tidak | belum terhubung |
| GitHub (repo) | github.com:22/443 | SSH/HTTPS | remote git | ya | aktif |
| Reverse proxy (VPS) | 127.0.0.1:8090 | HTTP | `GALARDO_BIND` | untuk produksi | lihat DEPLOY-VPS.md |

Catatan: default `make dev-up` TIDAK butuh koneksi eksternal sama sekali.

## P1. CI gate (GitHub Actions)
- Lokasi: `.github/workflows/gate.yml` (belum ada); sumber perintah: `make gate`.
- Kebutuhan: runner GitHub + Python 3.11 + `pip install -r requirements.txt`.
- Dampak bila absen: push bisa merusak tanpa terdeteksi; `make gate` bergantung disiplin manual.
- Lanjutan: workflow `on: push/pull_request` menjalankan `make test` + `make gate`,
  unggah log bila gagal, `timeout-minutes` tegas.
- Bukti: run pertama hijau di tab Actions; commit dengan sengaja dirusak -> CI merah.
- Estimasi: 1 blok. Prasyarat: izin repo.

## P2. Adapter provider proxy/residential (AnyIP dsb)
- Lokasi: `backend/proxypool.py` (ada), belum ada `backend/proxy_provider.py`.
  Kondisi: jalur residensial dicabut di STEP-54; belum ada pembaca kredensial provider.
- Kebutuhan: base URL + API key provider (mis. AnyIP), format respons untuk daftar IP:port.
- Dampak bila absen: rung ownership via proxy tak bisa memakai IP residensial;
  `proxypool` hanya memakai daftar statis.
- Lanjutan: adapter fail-open (pola `exttool`): `status()`, `daftar()`, `rotasi()`;
  env `GALARDO_PROXY_URL`, `GALARDO_PROXY_KEY`; endpoint `GET /api/v1/proxy/status`,
  `POST /api/v1/proxy/rotate` (TEST_OPERATOR); verifier offline (respons palsu) + live.
- Bukti: status melaporkan configured=true/false; rotasi mengembalikan IP baru.
- Estimasi: 1-2 blok. Prasyarat: kredensial dari Anda.

## P3. subfinder/nikto di image Docker
- Lokasi: `Dockerfile` + `requirements.txt`.
- Kebutuhan: unduh biner subfinder (GitHub release) & nikto (apt/perl) di image.
- Dampak bila absen: panel Tools di produksi tampil "TIDAK ADA" untuk keduanya.
- Lanjutan: layer `RUN` + verifikasi checksum; uji `docker compose exec galardo subfinder -version`.
- Bukti: `GET /api/v1/exttools` -> available=true untuk keduanya di container.
- Estimasi: 1 blok.

## P4. Rate limit / WAF dasar
- Lokasi: `backend/api.py` (belum ada limiter).
- Kebutuhan: token bucket per IP atau per token; env `GALARDO_RATE_LIMIT` (mis. `60/m`).
- Dampak bila absen: API terbuka bisa dibanjiri; tak ada pagar 429.
- Lanjutan: limiter in-process (stdlib), header `Retry-After`, endpoint terkecuali `/health`.
- Bukti: verifier menembak 70 request -> muncul 429; `make test` tetap hijau.
- Estimasi: 1 blok.

## P5. Pengerasan mode PG multi-proses
- Lokasi: `backend/db.py` (`_load()` hydrate sekali; `_state_mtime = inf`).
- Kondisi: file JSON = cermin; koherensi antar-proses hanya lewat PG saat satu proses.
- Lanjutan: hydrate ulang berkala (TTL pendek) atau `LISTEN/NOTIFY` PG untuk invalidasi.
- Bukti: dua proses menulis koleksi sama -> proses lain melihat perubahan dalam < TTL.
- Estimasi: 1 blok. Risiko: jangan sampai menimpa state lokal yang lebih baru.

## P6. Nonce CSP (buang unsafe-inline)
- Lokasi: `backend/api.py` (`CSP` memakai `'unsafe-inline'`), `dashboard/index.html` (satu file).
- Lanjutan: nonce per respons untuk `<script>` inline; `script-src 'nonce-...'`.
- Dampak bila absen: CSP lebih lemah dari seharusnya (masih ada pagar, tapi longgar).
- Bukti: verifier memastikan nonce ada dan cocok dengan atribut di HTML.
- Estimasi: 1 blok.

## Cara melanjutkan
Kerjakan urut P1 -> P6. Setiap selesai: catat di `docs/INVENTARIS.md` bila memunculkan
temuan, tulis `docs/HASIL-<n>.md`, `make gate` hijau, lalu commit + tag checkpoint.

---

## Lampiran A — env GALARDO_* yang benar-benar dipakai kode
```
GALARDO_API_PORT
GALARDO_BIND
GALARDO_CAP_PATH
GALARDO_CAP_PORT
GALARDO_CAP_SECONDS
GALARDO_CAP_START_TARGET
GALARDO_CAP_STEPS
GALARDO_CAP_WORKERS
GALARDO_CF_ACCOUNT_ID
GALARDO_CF_KEEP_DNS
GALARDO_CF_SCRIPT
GALARDO_CF_TEST_HOST
GALARDO_CF_TOKEN
GALARDO_CF_ZONE_ID
GALARDO_CF_ZONE_NAME
GALARDO_CORS_ORIGINS
GALARDO_CSP
GALARDO_DATA
GALARDO_DATA_DIR
GALARDO_DEMO_DURATION
GALARDO_DEMO_HEAVY_MS
GALARDO_DEMO_PORT
GALARDO_DEMO_SHIM_PORT
GALARDO_DEMO_VUS
GALARDO_DEMO_WORKERS
GALARDO_DEV_TOKEN
GALARDO_ENV
GALARDO_ENVELOPE_RESULT
GALARDO_EXTTOOL_TIMEOUT
GALARDO_JOB
GALARDO_K6_BIN
GALARDO_KNEE
GALARDO_KNEE_MAX_SEC
GALARDO_KNEE_SETTLE
GALARDO_KNEE_STEPS
GALARDO_KNEE_STEP_SEC
GALARDO_KNEE_TIMEOUT
GALARDO_KNEE_TTL
GALARDO_LADDER_SITE_PORT
GALARDO_LADDER_TEST_PORT
GALARDO_LOCAL_DEV
GALARDO_NATS_URL
GALARDO_NO_BUSTER
GALARDO_OTLP_URL
GALARDO_PG_DSN
GALARDO_PROXY_
GALARDO_REQUIRE_AUTH
GALARDO_SOURCES_PATH
GALARDO_SRC_PROBE_URL
GALARDO_SSDP_IFACE
GALARDO_TARGET_ORIGIN
GALARDO_TLS_TARGET
GALARDO_TRUST_MODE
GALARDO_UDP_BUDGET
GALARDO_WORKER_EXPERTISE
GALARDO_WORM_GRACE
GALARDO_WORM_TTL
```

## Lampiran B — jejak proxy/residential di kode
```
backend/identity_sim.py:10:- no third-party/residential proxies, no IP rotation services
backend/layer_attrib.py:25:    "ours": "cek egress/proxy kita dulu; jalankan probe ke target KONTROL",
backend/ownership.py:124:            "  TTL   : 300 (atau serendah yang diizinkan provider)",
backend/proxypool.py:1:"""GALARDO - resolusi nama pool proxy (HANYA untuk jalur probe).
backend/proxypool.py:3:Nama pool dipakai di skenario sebagai ``proxy_pool: "residential"``.
backend/proxypool.py:13:  2. variabel lingkungan ``GALARDO_PROXY_<NAMA>`` - mis. "host:port",
backend/proxypool.py:20:PREFIX = "GALARDO_PROXY_"
backend/proxypool.py:25:    """Spesifikasi proxy tidak sah."""
backend/proxypool.py:31:        raise PoolError("spesifikasi proxy kosong")
backend/proxypool.py:106:    """Pasang proxy pada transport. Kembalikan endpoint atau None.
backend/proxypool.py:108:    Toleran terhadap bentuk API transport: coba ``set_proxy(tuple)``,
backend/proxypool.py:109:    lalu ``set_proxy(host, port)``, lalu set atribut ``proxy``.
backend/proxypool.py:114:    setter = getattr(transport, "set_proxy", None)
backend/proxypool.py:122:                setattr(transport, "proxy", endpoint)
backend/proxypool.py:124:        setattr(transport, "proxy", endpoint)
backend/scenario.py:21:TOP_LEVEL = {"proxy_pool", "schema_version", "name", "description", "target_ref", "profile",
backend/scenario.py:77:    pp = doc.get("proxy_pool")
backend/scenario.py:81:                errors.append({"field": "proxy_pool", "code": "invalid_proxy_pool",
backend/scenario.py:82:                               "message": "proxy_pool must be a non-empty string"})
backend/scenario.py:85:                errors.append({"field": "proxy_pool", "code": "invalid_proxy_pool",
```

## Status per 2026-10-19

| Item | Status | Bukti |
|---|---|---|
| P1 CI gate | SELESAI | `.github/workflows/gate.yml` (58d8261). Terbukti hijau di Actions: run 1ea6864, 5f22956, 5d753ad, 34be942 (repo publik, dicek lewat API). |
| P2 proxy provider | SELESAI | `backend/proxy_provider.py` (752fccf + 0dda19b) + `tools/verify_proxy_provider.py`. Celah: tabrakan nama env dengan `proxypool`. |
| P3 subfinder/nikto | SELESAI | Dockerfile (d3d6d50) + panel exttools. |
| P4 rate limit | SELESAI | token bucket + 429 + Retry-After (a6935fc + 3f64fd9) + `tools/verify_ratelimit.py`. |
| P5 PG multi-proses | SELESAI | STEP-99: mtime cermin sebagai kanal deteksi + hydrate ulang dari PG + `tools/verify_pg_multiproc.py`. |
| P6 nonce CSP | SELESAI | STEP-98 (5f22956). |
| P7 botnet | usul | lihat docs/ROADMAP.md; belum masuk tabel PENDING. |

## Sisa PRD (otoritatif: docs/INVENTARIS.md)
- PENDING: item 9 botnet IoT global, item 2/3 lane proxy, item 4 transport multi-lane,
  V4 run nyata Mode Aktif, V6 4 check() tidak pernah dieksekusi.
- SEBAGIAN (kode ada, verifier khusus belum): item 10 DNS manipulation, item 13 UDP
  reflection, item 14 worm/lease.
- SELESAI: GOAL 2 observer tersambung, Tier 1, Tier 2, Tier 3.

