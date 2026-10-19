# GALARDO — Ringkasan Akhir & Panduan Resume

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
Angka pada daftar gate di atas berasal dari STEP-79. Angka terkini: make gate menjalankan
36 verifier; verify_headers 23/0, verify_dashboard_pages 16/0, verify_proxypool 27/0,
plus verifier baru verify_pg_multiproc 8/0. Semua dijalankan lewat `make gate` - tidak ada
lagi yang "dijalankan manual".
