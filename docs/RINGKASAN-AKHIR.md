# GALARDO — Ringkasan Akhir & Panduan Resume

> **STATUS TERKINI — diperbarui STEP-121, 2026-10-23**
>
> - PRD: **33 item SELESAI / 0 PENDING** (rujukan: `docs/INVENTARIS.md`, `docs/PENDING.md`)
> - gate: **rc=0** (37 verifier hijau) | test: **82 passed / 0 failed / 1 skipped**
> - LIVE: container `galardo nats otel pg`; seluruh port ter-bind `127.0.0.1`
> - dashboard: `http://127.0.0.1:8090/` — tempel token dari `.env` `GALARDO_DEV_TOKEN` di kotak kanan atas
> - auth: `GALARDO_REQUIRE_AUTH=1` (401 tanpa token, 200 dengan token); UI sudah punya kotak token
> - pihak ketiga **TERBUKTI**: `T3_OK` (Cloudflare edge) + `OWN1_OK` (ownership TXT, quorum DoH 3/3) — STEP-118
> - operasional: `make docker-up` / `make docker-down` / `make dev-up` / `make hijau` / `make ci`
>   (catatan: `make hijau` otomatis `docker compose stop galardo` karena port 8090 dipakai bersama)
> - backup: `tar -czf .out/backup/data-$(date +%Y%m%d).tgz data`
> - sisa **OPSIONAL**: TLS via Cloudflare Tunnel, `GALARDO_POOL_*` (lane rotate), `make capacity`, `gh` CLI
> - bukti mentah: `.out/STEP-115..121-*.txt`, rekaman `docs/HASIL-115..121.md`

Status: SELESAI. Backlog HANDOFF item 1-10 + P1-P6 tuntas. Temuan terbuka: NOL.

## Apa yang dikerjakan (item 1-10)
1-8 : netssl/knee/proxypool, audit dashboard, enam slice UI, Tier-1 (RBAC, MFA TOTP, backup, Docker)
9   : Tier 2-4 — NATS bus opt-in, alerting, ekspor OTLP, klien PostgreSQL wire, adapter db->PG
10  : run end-to-end nyata (lokal + Docker) dengan bukti mentah
Tambahan: integrasi tool eksternal (Subfinder/Nikto/Traceroute) + panel dashboard-nya.

## Invarian arsitektur (jangan dilanggar saat mengubah)
- Fail-open untuk layanan luar: netssl, pg, bus, otlp, exttool. Biner/URL tak ada != error.
- RBAC default-deny; peran: VIEWER < TEST_OPERATOR < APPROVER < ADMIN.
- Audit SELALU ditulis ke data/audit.jsonl (juga dimirror ke tabel PG saat mode PG).
- Semua rute API berprefix /api/v1 (lihat api.py: api_path = path[len("/api/v1"):]).
- Dashboard = satu file dashboard/index.html; nav + PAGE_TITLES + RENDER.<nama> WAJIB konsisten.
- Satu STEP = satu commit + docs/HASIL-<n>.md. Tak ada klaim tanpa bukti mentah.

## Cara resume di chat baru
Lampirkan (jangan riwayat chat):
    docs/ONBOARDING_PROMPT.txt
    docs/SESSION_STATE.md
    output: bash tools/resume.sh
Agen wajib melapor lebih dulu, lalu tunggu "lanjut". Detail disiplin: docs/RESILIENCE.md
(seksi 10 gate wajib, seksi 11 checklist pra-commit).

## Gate wajib sebelum commit
    bash tools/step_guard.sh
    bash tools/git_discipline.sh
    make test                    # acuan: 79 passed, 0 failed
    python3 tools/verify_netssl_wired.py    # 20/0
    python3 tools/verify_udp_budget.py      # 16/16
    python3 tools/verify_headers.py         # 22/0
    python3 tools/verify_exttool.py         # 16/0
    python3 tools/verify_dashboard_pages.py # 7/0
    python3 tools/verify_devup.py           # 2/2 (menyalakan dev-up)
Catatan: empat verifier terakhir TIDAK ikut `make test` (butuh port/jaringan), jadi
dijalankan manual di gate. Kandidat peningkatan: jadikan bagian make test-nya.

## Tag checkpoint (semua ter-push)
    checkpoint/galardo-v1.1-mulai
    checkpoint/galardo-v1.2-item9-tuntas
    checkpoint/galardo-v1.3-e2e-terbukti
    checkpoint/galardo-v1.4-header
    checkpoint/galardo-v1.5-exttool
    checkpoint/galardo-v1.6-tools-ui

## Temuan yang lahir DAN ditutup (register: docs/INVENTARIS.md seksi G)
F-1/F-1b dispatch 409; F-2 reklasifikasi; F-3 CSP; F-4 CORS; F-5 by-design;
F-7 probe UDP tanpa pagar; F-9..F-12 bug bus/alerts/_match/_g1; F-13 terminator startup;
F-14 SCRAM (5 sub-defect); F-15 db.all hilang; F-16 adapter salah baca (rows,err);
F-17 status tanpa probe; F-18 prefix probe; F-19 image tanpa dependensi; F-20 bind loopback;
F-21 f-string 3.12. Plus P0.1b urlopen tanpa netssl.context.
Pelajaran berulang: hijau offline != benar. Uji live + verifier AST menutup kelas bug ini.

## Risiko/sisa yang jujur
- Mode PG: SELESAI STEP-99 - koherensi antar-proses lewat mtime cermin + hydrate ulang dari PG
  (verifier tools/verify_pg_multiproc.py, dua proses nyata).
- CSP: SELESAI STEP-98 - nonce per-respons; 'unsafe-inline' hanya di direktif atribut.
- subfinder & nikto: ada di image (P3, commit d3d6d50).
- CI: ADA (P1) dan terbukti hijau - .github/workflows/gate.yml; run 1ea6864, 5f22956, 5d753ad, 34be942.
- P1-P6 SELESAI semua; sisa usul P7 (botnet) + Tier 3-4.
- Baris ROADMAP yang dulu dinormalkan: sebutan "VictoriaMetrics" opsional dikembalikan.

## Pembaruan STEP-102
Angka pada daftar gate di atas berasal dari STEP-79. Angka terkini: make hijau menjalankan
36 verifier; verify_headers 23/0, verify_dashboard_pages 16/0, verify_proxypool 27/0,
plus verifier baru verify_pg_multiproc 8/0. Semua dijalankan lewat `make hijau` - tidak ada
lagi yang "dijalankan manual".

> STATUS SEKARANG (kondisi terkini + blocker): `docs/STATUS-SEKARANG.md`

## STATUS TERKINI (STEP-171, 2026-10-24)
- HEAD saat blok ini ditulis: 655e992 feat(multilane): wiring orchestrator->engine gated GALARDO_MULTILANE + verifier AST/behavioral
- PONDASI SELESAI & TERVERIFIKASI (masing-masing punya verifier sendiri; gate menjalankan semuanya):
  doktrin GOAL + rantai onboarding; mesin pengguna & auth; netssl; headers; Mode B (gateway +
  proxypool + egress recorder, rantai pool->transport terbukti); origins (putus rantai edge->origin);
  intel + pre-flight (halaman Override + verifier HTTP live non-skip); check-host per-negara
  (+ endpoint POST /api/v1/checkhost); kapasitas/knee (kanonik tools/galardo_capacity.py, pembanding
  independen make capacity-fast); multi-lane di engine + wiring orchestrator (gated GALARDO_MULTILANE=1).
- BELUM (butuh Anda): (1) kredensial anyip.io -> set GALARDO_GATEWAY_URL lalu jalankan
  `python3 tools/verify_egress_rotation.py`; harus mencetak IP unik >= 2 (bukti rotasi egress nyata);
  (2) pihak ketiga live: `make tunnel` (mode cepat tanpa token, atau named tunnel bila
  GALARDO_CF_TUNNEL_TOKEN diisi).
- CARA LANJUT DI CHAT BARU: baca docs/GOAL-GALARDO.md (MENGIKAT) lalu docs/STATUS-SEKARANG.md;
  jalankan `make hijau` (SEMUA tools/verify_*.py) dan `make test` sebelum menyentuh apa pun.
- ATURAN KERJA: bukti mentah dulu sebelum menambal; cek struktur via AST/behavioral (bukan teks);
  angka rc ditulis apa adanya; patch idempoten; commit + push tiap langkah hijau.

## V1.4 (cap 2026-10-25)
Versi: GALARDO V1.4. Baca docs/V1.4.md + docs/TARGET-BUKTI.md. Sisa: kredensial anyip.io,
bukti rotasi egress, lalu pindah VPS dan bukti BEBAN pada wecash.ai + waspadaweb.com.
