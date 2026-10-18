# DEPLOY GALARDO DI VPS — panduan langkah demi langkah

Asumsi: Ubuntu 22.04/24.04, akses sudo, Docker + plugin compose terpasang,
satu domain (mis. `galardo.contoh.com`) dengan A-record ke IP VPS.

Galardo = SATU container API + dashboard (port internal 8090) + opsional pg/nats/otel.
Default jalan tanpa kredensial apa pun. Semua integrasi fail-open.

## 0. Prasyarat yang HARUS Anda siapkan
- [ ] Domain + A-record ke IP VPS
- [ ] SSH key (login non-root, sudo)
- [ ] Docker Engine + `docker compose` plugin
- [ ] Token API kuat untuk GALARDO_DEV_TOKEN (JANGAN pakai default `dev-token`)
- [ ] Opsional: token Cloudflare + nama zona (untuk `make t3`)
- [ ] Opsional: credential provider proxy/residential (AnyIP dsb) — BELUM diintegrasikan
- [ ] Opsional: `subfinder` & `nikto` bila ingin dijalankan dari panel Tools

## 1. Verifikasi dulu di lokal (jangan deploy kalau merah)
    make gate            # harus rc=0 (make test + SEMUA verifier)
    make demo            # harus verdict RECOVERED + override 404/blank forced

## 2. Siapkan VPS
    ssh deploy@IP
    sudo adduser --disabled-password galardo && sudo usermod -aG docker galardo
    sudo apt update && sudo apt install -y git curl ufw
    sudo -u galardo git clone git@github.com:eghi1818/Galardo.git ~/galardo
    cd ~/galardo

## 3. .env produksi (WAJIB diganti)
    cat > .env <<'ENV'
    GALARDO_DEV_TOKEN=ganti-dengan-token-panjang-acak
    GALARDO_BIND=0.0.0.0
    GALARDO_CORS_ORIGINS=https://galardo.contoh.com
    # opsional (biarkan kosong bila tak dipakai):
    # GALARDO_PG_DSN=postgres://galardo:RAHASIA@pg:5432/galardo
    # GALARDO_NATS_URL=nats://nats:4222
    # GALARDO_OTLP_URL=http://otel:4318
    # GALARDO_CF_TOKEN=...
    ENV
    chmod 600 .env

Catatan: `GALARDO_BIND=0.0.0.0` WAJIB di container (kalau 127.0.0.1, port publish mati — F-20).
`GALARDO_CORS_ORIGINS` diisi domain asli supaya CORS strict, bukan `*`.

## 4. Override compose (JANGAN ubah file repo)
Buat `docker-compose.override.yml`:

    services:
      galardo:
        ports:
          - "127.0.0.1:8090:8090"     # hanya reverse proxy yang lihat
        restart: unless-stopped
        volumes:
          - ./data:/app/data          # WAJIB: audit + state + backup jangan hilang
        environment:
          GALARDO_DEV_TOKEN: ${GALARDO_DEV_TOKEN}

Port di-bind ke 127.0.0.1 supaya 8090 tidak terbuka langsung ke internet.

## 5. Jalankan
    docker compose up -d --build
    docker compose ps                      # galardo harus Up (healthy)
    docker inspect --format '{{.State.Health.Status}}' galardo-local

## 6. Verifikasi
    curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/api/v1/health   # 200
    curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/                # 200
    TOK=$(grep GALARDO_DEV_TOKEN .env | cut -d= -f2-)
    curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOK" \
      http://127.0.0.1:8090/api/v1/exttools                                        # 200

## 7. Reverse proxy + TLS (Caddy = paling ringkas, TLS otomatis)
    sudo apt install -y caddy
    sudo tee /etc/caddy/Caddyfile >/dev/null <<'CADDY'
    galardo.contoh.com {
        reverse_proxy 127.0.0.1:8090
    }
    CADDY
    sudo systemctl reload caddy
    curl -sI https://galardo.contoh.com/api/v1/health | head -n 1     # 200

Alternatif nginx: proxy_pass http://127.0.0.1:8090; + certbot.

## 8. Firewall
    sudo ufw allow 22,80,443/tcp
    sudo ufw deny 8090/tcp
    sudo ufw enable

## 9. Backup otomatis (harian, retensi 7)
    mkdir -p ~/galardo/backups
    crontab -e   # tambahkan:
    15 3 * * * cd ~/galardo && /usr/bin/make backup KEEP=7 >> ~/backup.log 2>&1
    # verifikasi: make backup-verify

## 10. Observability (opsional)
    docker compose up -d nats otel pg
    # arahkan GALARDO_OTLP_URL ke collector; alerting: POST /api/v1/alerts

## 11. Upgrade / rollback
    git fetch --tags && git checkout checkpoint/galardo-v1.6-tools-ui
    docker compose up -d --build
    # rollback: git checkout <tag-lama> && docker compose up -d --build

## 12. Checklist keamanan produksi
- [ ] GALARDO_DEV_TOKEN diganti (default `dev-token` = bahaya di internet)
- [ ] 8090 di-bind ke 127.0.0.1, hanya 80/443 terbuka
- [ ] TLS aktif (Caddy/certbot)
- [ ] GALARDO_CORS_ORIGINS = domain asli (bukan `*`)
- [ ] CSP aktif (default sudah ada; override via GALARDO_CSP bila perlu)
- [ ] `data/` sebagai volume + backup harian terverifikasi
- [ ] container `restart: unless-stopped`
- [ ] login SSH non-root + key only
- [ ] `make gate` dijalankan setiap habis upgrade

## 13. Yang BELUM ada (jujur)
- Belum ada CI: `make gate` masih manual
- Credential provider proxy/residential (AnyIP dsb) belum diintegrasikan
- `subfinder`/`nikto` tidak ada di image; install di image bila mau dipakai produksi
- Mode PG mengasumsikan satu proses aplikasi (file JSON = cermin)
- Belum ada rate limit / WAF; andalkan reverse proxy

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

## Lampiran B — layanan & port di docker-compose
```
2:  galardo:
4:    image: galardo:local
5:    container_name: galardo-local
6:    ports:
27:  nats:
28:    image: nats:2.10-alpine
29:    container_name: galardo-nats
31:    ports:
36:  otel:
37:    image: otel/opentelemetry-collector-contrib:0.104.0
38:    container_name: galardo-otel
42:    ports:
46:  pg:
47:    image: postgres:16-alpine
48:    container_name: galardo-pg
53:    ports:
65:  pgdata:
```

## Lampiran C — Dockerfile (base + ENV + CMD)
```
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GALARDO_BIND=0.0.0.0

EXPOSE 8090 8095 8899

HEALTHCHECK --interval=10s --timeout=5s --retries=6 \
  CMD python3 -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/api/v1/health').status==200 else 1)"

CMD ["python3", "backend/run_local.py"]
```

## Lampiran D — target Makefile yang relevan untuk operasi
```
22:dev-up:
25:dev-down:
33:test:
63:demo:
117:backup:
119:backup-verify:
124:docker-verify:
126:docker-build:
128:docker-up:
130:docker-down:
133:gate: test
```
