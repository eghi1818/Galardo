# KONEKSI PIHAK KETIGA — panduan daftar, pasang, dan uji

Prinsip: SEMUA opsional. Galardo fail-open — layanan tak dikonfigurasi != error.
Kredensial jangan pernah di-commit: simpan di `.env` (chmod 600) atau GitHub Secrets.

## 0. Ringkasan: mana yang perlu daftar
| Layanan | Perlu daftar? | Untuk apa | Status di kode |
|---|---|---|---|
| GitHub | sudah punya | repo + CI | ada (workflow .github/workflows/gate.yml) |
| Cloudflare | ya | uji 404/blank ke domain asli (`make t3`) | ada, kredensial BELUM diisi |
| PostgreSQL (lokal/cloud) | cloud: ya | penyimpanan produksi | ada (fail-open) |
| NATS | opsional | bus event | ada (opt-in) |
| OTLP collector | opsional | telemetri | ada (opt-in) |
| Provider proxy/residential | ya | IP residensial utk rung ownership | kode SELESAI (STEP-114, backend/proxy.py); kredensial belum diisi (P2 PENDING.md) |
| DNS resolver | tidak | probe UDP + ownership dns_txt | ada (pakai 1.1.1.1/8.8.8.8) |
| VPS + domain | ya | tempat berjalan | n/a (lihat DEPLOY-VPS.md) |

## 1. GitHub (sudah beres)
Repo: github.com/eghi1818/Galardo. CI: tab Actions → workflow `gate`.
Uji: buka tab Actions, pastikan run terakhir hijau.

## 2. Cloudflare — untuk `make t3` (uji 404/blank ke domain asli)
1. Daftar/masuk: https://dash.cloudflare.com
2. Add a site → masukkan domain → pilih plan Free → ikuti instruksi ganti nameserver
   di registrar domain Anda (proses propagasi bisa sampai beberapa jam).
3. Buat API Token: kanan atas → My Profile → API Tokens → Create Token →
   "Create Custom Token":
   - Permissions: Zone → Zone → Read, dan Zone → DNS → Read (tambah DNS → Edit bila
     ingin Galardo mengubah record)
   - Zone Resources: Include → Specific zone → domain Anda
4. Salin dua nilai: **API Token** dan **Zone ID** (di halaman Overview domain,
   kolom kanan bawah).
5. Set di Galardo (nama env dari kode - lihat Lampiran A/B):
       GALARDO_CF_TOKEN=<api token>
       GALARDO_CF_ACCOUNT_ID=<account id>
       GALARDO_CF_ZONE_ID=<zone id>          # atau GALARDO_CF_ZONE_NAME=<domain>
6. Uji: `make t3` → harus mencetak status/verdict, bukan 401/403.
Catatan: zona Cloudflare hanya perlu kalau Anda mau uji live; tanpa itu `make dev-up`
tetap jalan penuh.

## 3. PostgreSQL — penyimpanan produksi (opsional; lokal sudah via compose)
Opsi A (lokal, tanpa daftar): `docker compose up -d pg`
Opsi B (cloud, gratis): https://neon.tech
1. Daftar → New Project → pilih region terdekat.
2. Salin connection string: `postgres://USER:PASS@HOST/DB?sslmode=require`
3. Set `GALARDO_PG_DSN=<string itu>`
4. Uji:
       python3 tools/verify_pg.py                 # offline: 35 cek
       python3 - <<'PY'
       import os,sys; sys.path.insert(0,"backend")
       import pg; c=pg.connect(); print(c.query("select version()")[0]); c.close()
       PY
Catatan: tanpa DSN, Galardo memakai JSON lokal (fallback). Tabel dibuat otomatis
(`galardo_docs`, `galardo_audit`).

## 4. NATS — bus event (opsional)
Opsi A: `docker compose up -d nats` → `GALARDO_NATS_URL=nats://nats:4222`
Opsi B (cloud): https://synadia.cloud → daftar → dapat URL + kredensial
(nats://user:pass@host:4222). Set ke `GALARDO_NATS_URL`.
Uji: `python3 tools/verify_bus.py` → semua hijau.

## 5. OTLP — telemetri (opsional)
Opsi A: `docker compose up -d otel` → `GALARDO_OTLP_URL=http://otel:4318`
Opsi B (cloud): Grafana Cloud → Connections → OpenTelemetry (dapat endpoint + header
Authorization), atau Honeycomb → endpoint + header `x-honeycomb-team`.
Set `GALARDO_OTLP_URL` (dan header bila kode mendukung — cek Lampiran A).
Uji: `python3 tools/verify_otlp.py` hijau, lalu lihat data muncul di provider.

## 6. Provider proxy/residential (AnyIP dsb) — kode SELESAI (STEP-114, backend/proxy.py); kredensial belum diisi
Pilihan populer: AnyIP, Bright Data, IPRoyal, Smartproxy.
1. Daftar di salah satu, ambil paket terkecil dulu untuk uji.
2. Salin: **API base URL**, **API key/token**, dan contoh format daftar proxy
   (biasanya `host:port` + `user:pass`, atau respons JSON).
3. Galardo sudah membacanya (P2). Env: `GALARDO_PROXY_URL`, `GALARDO_PROXY_KEY`
   (opsional `GALARDO_PROXY_AUTH`, `GALARDO_PROXY_POOL`, `GALARDO_PROXY_TTL`,
   `GALARDO_PROXY_TIMEOUT`); endpoint `GET /api/v1/proxy/status`,
   `POST /api/v1/proxy/refresh`, `POST /api/v1/proxy/rotate`.
4. Kirim ke saya: base URL + bentuk responsnya (key apa saja) supaya adapter-nya
   ditulis sesuai API provider Anda, bukan diasumsikan.

## 7. DNS resolver — tidak perlu daftar
Kode memakai resolver publik (1.1.1.1/8.8.8.8). Kalau mau custom, ubah daftar di
`backend/udp_probe.py` (DNS_CANDIDATES).

## 8. VPS + domain
VPS: Hetzner / DigitalOcean / Vultr → daftar → create Ubuntu 24.04 → tempel SSH key →
firewall 22/80/443. Domain: registrar → A record ke IP VPS (atau lewat Cloudflare).
Langkah lengkap: `docs/DEPLOY-VPS.md`.

## 9. Cara menyimpan kredensial dengan aman
- Lokal/VPS: file `.env` (chmod 600), jangan di-commit (sudah di .gitignore).
- Docker: pakai `docker-compose.override.yml` + `environment:` (lihat DEPLOY-VPS.md).
- GitHub Actions: Settings → Secrets and variables → Actions → New repository secret.
- Cek cepat: `grep -c '=' .env` dan pastikan tidak ada token yang tampil di `git status`.

## 10. Kalau berhasil / gagal, kelihatannya bagaimana
| Layanan | Tanda berhasil | Tanda gagal yang umum |
|---|---|---|
| Cloudflare | `make t3` mencetak verdict | 401 (token salah), 403 (scope kurang) |
| PostgreSQL | `select version()` keluar | `ConnectionRefusedError`, `auth gagal` |
| NATS | verify_bus hijau | koneksi ditolak / timeout |
| OTLP | data muncul di provider | 404/401 dari collector |
| Provider proxy | status `configured: true` | 401/403 dari API provider |
Semua kegagalan di atas TIDAK mematikan Galardo — hanya fiturnya yang absen.

---

## Lampiran A — env GALARDO_* di kode (sumber kebenaran)
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
GALARDO_POOL_
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

## Lampiran B — di mana tiap env dibaca (grep)
```
backend/routeoverride.py:574:        self.token = token or os.environ.get("GALARDO_CF_TOKEN")
backend/routeoverride.py:575:        self.account_id = account_id or os.environ.get("GALARDO_CF_ACCOUNT_ID")
backend/routeoverride.py:576:        self.zone_id = zone_id or os.environ.get("GALARDO_CF_ZONE_ID")
backend/routeoverride.py:588:            m.append("GALARDO_CF_TOKEN")
backend/routeoverride.py:590:            m.append("GALARDO_CF_ACCOUNT_ID")
backend/routeoverride.py:592:            m.append("GALARDO_CF_ZONE_ID")
backend/routeoverride.py:599:        zone_name = zone_name or os.environ.get("GALARDO_CF_ZONE_NAME")
backend/routeoverride.py:621:                    out["errors"].append("token melihat %d zone; set GALARDO_CF_ZONE_NAME"
backend/routeoverride.py:763:        self.script = script or os.environ.get("GALARDO_CF_SCRIPT", "galardo-override")
backend/routeoverride.py:764:        self.host = host or os.environ.get("GALARDO_CF_TEST_HOST")
backend/routeoverride.py:769:        self.keep_dns = (os.environ.get("GALARDO_CF_KEEP_DNS", "1") != "0") \
backend/routeoverride.py:795:                              "tidak bisa baca zone (cek GALARDO_CF_ZONE_ID + izin token)")
backend/pg.py:3:Aktif hanya bila GALARDO_PG_DSN diisi. Auth didukung: trust, cleartext, md5,
backend/pg.py:15:DSN_ENV = "GALARDO_PG_DSN"
backend/otlp.py:3:Aktif hanya bila GALARDO_OTLP_URL diisi (mis. http://127.0.0.1:4318).
backend/otlp.py:20:    return bool((os.environ.get("GALARDO_OTLP_URL") or "").strip())
backend/otlp.py:106:    u = url or os.environ.get("GALARDO_OTLP_URL") or "http://127.0.0.1:4318"
backend/api.py:39:CORS_ENV = "GALARDO_CORS_ORIGINS"
backend/api.py:40:CSP = os.environ.get("GALARDO_CSP") or (
backend/api.py:64:DEV_TOKEN = os.environ.get("GALARDO_DEV_TOKEN", "dev-token")  # MVP lab: seeded dev users only
backend/db_pg.py:4:- Aktif HANYA bila GALARDO_PG_DSN diisi DAN koneksi + DDL berhasil.
backend/db_pg.py:30:    """True bila GALARDO_PG_DSN terisi (belum berarti koneksinya hidup)."""
backend/db_pg.py:87:            _reason = "GALARDO_PG_DSN kosong"
backend/bus.py:3:Aktif hanya bila GALARDO_NATS_URL diisi. Tanpa itu -> no-op (polling tetap jalan).
backend/bus.py:18:    return bool((os.environ.get("GALARDO_NATS_URL") or "").strip())
backend/bus.py:34:    url = (os.environ.get("GALARDO_NATS_URL") or "").strip()
backend/nats_client.py:5:abort fanout. Set GALARDO_NATS_URL=nats://127.0.0.1:4222 to enable.
backend/nats_client.py:143:    url = url or os.environ.get("GALARDO_NATS_URL")
backend/proxypool.py:13:  2. variabel lingkungan ``GALARDO_POOL_<NAMA>`` - mis. "host:port",
backend/proxypool.py:21:POOL_PREFIX = "GALARDO_POOL_"
```

## Lampiran C — jejak proxy/residential (untuk P2)
```
backend/proxypool.py:3:Nama pool dipakai di skenario sebagai ``proxy_pool: "residential"``.
```
