# SESSION_STATE — Galardo

> **BACA WAJIB (setiap chat, tanpa kecuali): `docs/GOAL-GALARDO.md`.**
> Tujuan Galardo = membuat target MATI / tidak bisa diakses (Layer 7; target payment
> gateway seperti DOKU -> Akamai Reference #102 / halaman fallback / circuit breaker).
> Wajib: multi-IP (pool/rotasi), request sah secara sintaksis, asimetri di endpoint berat,
> targeting dari intel REA, dan memutus rantai edge->origin. Kalau benturan soal TUJUAN,
> GOAL-GALARDO.md yang menang. Anti-pola terlarang ada di sana.

> **STATUS TERKINI — diperbarui STEP-121, 2026-10-23**
>
> - PRD: **33 item SELESAI / 0 PENDING** (rujukan: `docs/INVENTARIS.md`, `docs/PENDING.md`)
> - gate: **rc=0** (37 verifier hijau) | test: **82 passed / 0 failed / 1 skipped**
> - LIVE: container `galardo nats otel pg`; seluruh port ter-bind `127.0.0.1`
> - dashboard: `http://127.0.0.1:8090/` — tempel token dari `.env` `GALARDO_DEV_TOKEN` di kotak kanan atas
> - auth: `GALARDO_REQUIRE_AUTH=1` (401 tanpa token, 200 dengan token); UI sudah punya kotak token
> - pihak ketiga **TERBUKTI**: `T3_OK` (Cloudflare edge) + `OWN1_OK` (ownership TXT, quorum DoH 3/3) — STEP-118
> - operasional: `make docker-up` / `make docker-down` / `make dev-up` / `make gate` / `make ci`
>   (catatan: `make gate` otomatis `docker compose stop galardo` karena port 8090 dipakai bersama)
> - backup: `tar -czf .out/backup/data-$(date +%Y%m%d).tgz data`
> - sisa **OPSIONAL**: TLS via Cloudflare Tunnel, `GALARDO_POOL_*` (lane rotate), `make capacity`, `gh` CLI
> - bukti mentah: `.out/STEP-115..121-*.txt`, rekaman `docs/HASIL-115..121.md`

Diperbarui : STEP-102 (2026-10-19)
HEAD       : lihat `git log -1` atau output tools/resume.sh (jangan simpan hash di sini)
Branch     : main (sinkron origin/main)
Titik aman : tag terakhir `git tag -l | tail -n 1`; branch checkpoint/galardo-v1.* masih ada

## Status
- P1-P6 (docs/PENDING.md): SELESAI semua. P1 CI terbukti hijau di tab Actions.
- F-1..F-24, P0.1b, P0.2, Tier 1-2: TUTUP. Rincian docs/INVENTARIS.md + docs/STEPLOG.md.
- SISA (otoritatif docs/INVENTARIS.md): V4 run nyata Mode Aktif (V6 4 check() mati sudah TUTUP STEP-104).
  Tier 1-3 SELESAI; P7 = nama lain item 9. Item 10/13/14 SEBAGIAN, GOAL 2 SELESAI.

## Konvensi
- Keluaran mentah STEP -> .out/  (docs/CONTEXT.md)
- Rekaman per STEP     -> docs/HASIL-<step>.md (satu tempat)
- Gate wajib sebelum commit: make gate && make test (docs/RESILIENCE.md bagian 10)

## Baru-baru ini (jangan dikerjakan ulang)
- STEP-98  : P6 nonce CSP per-respons; 2 verifier diperkuat.
- STEP-99  : P5 koherensi db multi-proses; tools/verify_pg_multiproc.py.
- STEP-100 : namespace env pool GALARDO_POOL_ (warisan GALARDO_PROXY_ tetap dibaca,
             kecuali nama reserved milik provider).
- STEP-101 : rekonsiliasi dokumen + node di CI.
- STEP-102 : dokumen handoff ini disegarkan.

## Langkah berikut
Baca docs/PENDING.md (bagian Status) dan docs/HANDOFF.md bagian 8.
Jangan buka lebih dari satu item sekaligus.
