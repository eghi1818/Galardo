# STEPLOG — riwayat langkah

| STEP | Isi | Hasil |
|---|---|---|
| 01 | fix 2 FAIL verifikasi trust | 39/0 hijau |
| 02 | commit + intel Makefile | hijau |
| 03 | push + tarik dokumen rencana | hijau |
| 04 | lacak W4 + siapkan ownership | hijau |
| 05 | inventaris + lacak REA | hijau |
| 06 | amankan + kirim file | hijau |
| 07 | Fase A patch 1: ownership_ladder.py | 27/0 hijau |
| 08 | alat bundel + docs/HANDOFF.md | hijau |
| 09 | audit lokasi + fix bundle (zsh) | hijau |
| 10 | adopsi .git ke path kanonik | hijau (10B lanjutan) |
| 10B | selesaikan adopsi + arsip folder lama | hijau |
| 11 | Fase A patch 2: endpoint tangga di api.py | 18/0 hijau |
| 12 | disiplin git 4 lapis + hook auto-push | hijau |
| 13 | cache buster + deteksi cache HIT | 36/0 hijau |
| 14 | handoff darurat + wiring cache buster | hijau (engine/scenario/step_load) |
| 15 | fix import os step_load + smoke.sh | 59/0 + smoke OK |
| 16 | first-prompt ke repo + selaraskan dokumen | hijau |
| 17 | ONBOARDING_PROMPT.md sumber tunggal | hijau |
| 18 | atribusi lapisan verdict | 32/0 hijau |
| 19 | satukan penanda cache buster ke __gb | 18/0 hijau |
| 20 | bersihkan _gcb sisa + atribusi lapisan di probe | lihat HASIL-20 |
| 21 | verifikasi token CF + status zone + uji tulis DNS | hijau (TLS salah diagnosa) |
| 22 | TLS doctor awal + netssl + catat STEPLOG 21 | hijau |
| 23 | TLS doctor benar + netssl wired ke probe | lihat HASIL-23 |
| 24 | external_probe pakai netssl (regex, gagal lalu diperbaiki) |
| 25 | fix netssl + _opener + persona + roadmap berjenjang |
| 26 | P0.1 migrasi semua modul HTTPS ke netssl | lihat HASIL-26 |
| 27 | persona final + docs/INVENTARIS.md + verifikasi defect | lihat HASIL-27 |
| 28 | defect D5-D14 terverifikasi selesai + intel auto-knee | lihat HASIL-28 |
| 29 | P0.2a modul estimasi knee (tes menangkap 1 cacat) |
| 30 | perbaiki semantik plateau relatif + tes H |
| 31 | bedah orchestrator.py (langkah baca) |
| 32 | P0.2b knee_probe + sambung ke preflight |
| 33 | ok_rps: plafon dari throughput berhasil |
| 34 | kalibrasi delta plateau untuk ramp thread sublinear |
| 35 | TTL cache knee + biaya probe lebih murah |
| 36 | pagar anggaran waktu knee + peringatan preflight lambat | lihat HASIL-36 |
| 37 | audit dashboard/ - ternyata SUDAH ADA (index.html 1205 baris) |
| 38 | cache knee per origin |
| 39 | check knee wajib PASS + probe tidak mengganggu baseline |
| 40 | diagnosa 2 tes merah knee_probe + fix cache tes E | lihat HASIL-40 |
| 41 | fix tes E3 (path probe_contract) + hijaukan verify_knee_probe | lihat HASIL-41 |
| 42 | peta celah UI vs API (dokumen kerja P2) | lihat HASIL-42 |
| 43 | peta celah UI vs API v2 (ekstraksi dispatch asli) | lihat HASIL-43 |
| 44 | peta celah UI vs API v3 (scan _dispatch penuh + method) | lihat HASIL-44 |
| 45 | konfirmasi GAP, bersihkan artefak, backlog P2 berprioritas | lihat HASIL-45 |
| 46 | V4: dump permukaan run + percobaan hidup + rencana E2E | lihat HASIL-46 |
| 47 | V4: jalankan harness e2e (make demo) + rekam hasil | lihat HASIL-47 |
| 48 | P1.5: uji T3 live koler.space (paksa 404/blank lewat edge) | lihat HASIL-48 |
| 49 | P1.3: terima field proxy_pool di skema skenario | lihat HASIL-49 |
| 50 | proxy_pool di TOP_LEVEL + validasi + 2 tes (pintu probe residential) | lihat HASIL-50 |
| 51 | proxy_pool mengalir ke dokumen ternormalisasi + verifier | lihat HASIL-51 |
| 52 | verifier proxy_pool: targets_by_name + cek ketat | lihat HASIL-52 |
| 53 | registry sumber: buka kapabilitas residential | lihat HASIL-53 |
| 54 | cabut residential dari SUPPORTED_ENCODINGS + resolver proxypool | lihat HASIL-54 |
| 54b | kit ketahanan sesi: SESSION_STATE + RESILIENCE + resume.sh | lihat docs/RESILIENCE.md |
| 55 | P1.4: bukti e2e rung dns_txt (rank 4) di koler.space + verifier + tes | lihat HASIL-55 |
| 56 | sinkron audit dashboard: item 6 SELESAI + upgrade DASHBOARD-AUDIT.md + temuan F-2..F-4 | lihat docs/HASIL-56.md |
| 57 | tutup F-2 sebagai reklasifikasi (path target, bukan route API) + koreksi UI-API-GAP | lihat docs/HASIL-57.md |
| 58 | panel Ownership di dashboard (irisan 1/6 item 7) + verifier halaman + F-6 | lihat docs/HASIL-58.md |
| 59 | panel Sources di dashboard (irisan 2/6 item 7) | lihat docs/HASIL-59.md |
| 60 | kartu Bukti & observer di halaman live (irisan 3/6 item 7) + tutup F-1 | lihat docs/HASIL-60.md |
| 60c | tutup F-1 dengan sebab akurat (toleransi 409 preflight) + F-7 timeout udp | lihat docs/HASIL-60c.md |
| 61 | halaman Overrides di dashboard (irisan 4/6 item 7) | lihat docs/HASIL-61.md |
| 62 | editor probe-contract di tabel Targets (irisan 5/6 item 7) | lihat docs/HASIL-62.md |
| 63 | halaman Webhooks + remote-dispatch (irisan 6/6 item 7) - ITEM 7 TUTUP | lihat docs/HASIL-63.md |
| 64 | RBAC inti: backend/rbac.py + tools/verify_rbac.py + endpoint /me,/users,/users/*/role + 5 cek integrasi | lihat docs/HASIL-64.md |
| 65 | MFA TOTP: backend/mfa.py + tools/verify_mfa.py (vektor RFC 6238) + /me/mfa/{enroll,verify,disable} + 5 cek integrasi | lihat docs/HASIL-65.md |
| 66 | backup otomatis: tools/backup.py + verify_backup + target make, retensi, restore | lihat docs/HASIL-66.md |
| 67 | Docker Compose + Dockerfile + verify_compose + dukungan GALARDO_BIND - ITEM 8 TUTUP | lihat docs/HASIL-67.md |
| 68 | bus NATS opt-in (fail-open) + service nats di compose + verify_bus | lihat docs/HASIL-68.md |
| 69 | alerting + F-9..F-12 (bus, _match list, bootstrap peran, _g1 rekursi) | lihat docs/HASIL-69.md |
| 70 | ekspor OTLP/HTTP JSON (metrics+span) + service otel-collector | lihat docs/HASIL-70.md |
| 71 | klien PostgreSQL minimal (wire v3, scram/md5) + service pg + uji live + F-13/F-14 (terminator startup, SCRAM, vektor RFC 7677, F-1b anggaran retry) | lihat docs/HASIL-71.md |
| 72 | adapter db -> PostgreSQL dengan fallback JSON (db_pg.py, cermin JSON, fail-open) + F-15/F-16/F-17 | lihat docs/HASIL-72.md |
| 73 | e2e nyata: jalur lokal (demo DOWN->RECOVERED, 404/blank) + jalur Docker sehat (port publish 200) + F-18/F-19/F-20/F-21 | lihat docs/HASIL-73.md |
| 74 | P0.1b TUTUP: urlopen tanpa netssl.context di 4 modul + verifier urlopen/AST + verify_devup | lihat docs/HASIL-74.md |
| 75 | F-7 TUTUP: probe UDP berpagar waktu (budget total + deadline fan-out + clamp per-target) | lihat docs/HASIL-75.md |
| 76 | F-3/F-4 TUTUP: CSP + header keamanan + CORS terkonfigurasi (strict) + verifier header | lihat docs/HASIL-76.md |
| 77 | integrasi tool eksternal Subfinder/Nikto/Traceroute (fail-open) + endpoint /exttools | lihat docs/HASIL-77.md |
| 78 | panel dashboard Tools (status tool + form jalankan + hasil) untuk subfinder/nikto/traceroute | lihat docs/HASIL-78.md |
| 79 | penutup: ringkasan akhir + panduan resume (docs/RINGKASAN-AKHIR.md) | - |
| 80 | F-22 TUTUP: verify_knee_probe deterministik + target make gate (semua verifier masuk gate) | lihat docs/HASIL-80.md |
| 81 | e067229 - docs: panduan deploy VPS + lampiran env/port/compose | - |
| 82 | 58d8261 - docs+ci: rincian pending (PENDING.md) + CI gate GitHub Actions | - |
| 83 | 1f68974 - docs: panduan pendaftaran koneksi pihak ketiga | - |
| 84 | 752fccf - P2: adapter provider proxy/residential (fail-open) + endpoint | - |
| 85 | 0dda19b - fix proxy: hook resolve() 2-tuple + verifier pakai env_key | lihat docs/HASIL-85.md |
| 86 | d3d6d50 - P3: subfinder + nikto tersedia di image | - |
| 87 | a6935fc - P4: rate limit (token bucket, 429 + Retry-After) | lihat docs/HASIL-87.md |
| 88 | 3f64fd9 - fix rate limit: kunci tanpa skema auth + cek gate pakai exit code | lihat docs/HASIL-88.md |
| 89-96 | jendela tanpa commit berlabel STEP; tidak ada docs/HASIL-89..96 | - |
| 97 | F-1b & F-24 ditutup pada akarnya (409 konflik=retryable; uji replay pakai kode ter-cache) + verifier verify_start_reject (9 cek) masuk gate; 42 run bersih | lihat docs/HASIL-97.md |

Acuan tes: make test 79/79, verify_db_pg 46/46, verify_pg 35/35, verify_netssl_wired 20/20, verify_udp_budget 16/16, verify_headers 22/22, verify_exttool 16/16, verify_dashboard_pages 7/7, verify_devup 2/2, verify_start_reject 9/9, smoke.sh. Titik aman: tag v1.7 (250c713)
| 98 | P6 TUTUP: nonce CSP per-respons (script-src/style-src ber-nonce, 'unsafe-inline' hanya di direktif atribut); verifier dashboard & headers diperkuat (regex toleran atribut, cek nonce & _csp runtime) | lihat docs/HASIL-98.md |
| 99 | P5 TUTUP: koherensi db multi-proses (mtime cermin sebagai kanal deteksi, mode PG hydrate ulang dari PG) + verify_pg_multiproc | lihat docs/HASIL-99.md |
| 100 | P2 lanjutan: pool proxy pindah ke namespace GALARDO_POOL_ (warisan GALARDO_PROXY_ tetap dibaca kecuali nama reserved) + cek tabrakan di verifier | lihat docs/HASIL-100.md |
| 101 | rekonsiliasi dokumen (KONEKSI/DEPLOY env pool, ROADMAP sisa, EMERGENCY acuan 79, gate.yml +setup-node & pola FAIL) + backfill STEPLOG 81-96 | lihat docs/HASIL-101.md |
| 102 | segarkan dokumen handoff (SESSION_STATE, RINGKASAN-AKHIR, HANDOFF 8/8b/9, PENDING caveat P1, resume.sh) + P1 terbukti hijau di Actions | lihat docs/HASIL-102.md |
| 103 | koreksi status INVENTARIS dari kode+verifier (item 10/13/14 SEBAGIAN, GOAL 2 SELESAI, seksi E) + koreksi daftar SISA di SESSION_STATE/HANDOFF/PENDING + diagnosis V6 | lihat docs/HASIL-103.md |
| 104 | V6 TUTUP: check() di cabang mati kini selalu melapor (SKIP) + penjaga "semua nama check() melapor" + INVENTARIS V2/V6 dikoreksi | lihat docs/HASIL-104.md |
| 105 | penutupan dokumen STEP-104 (INVENTARIS V2/V6, STEPLOG 104, koreksi HASIL-104) + baca jangkar jalur recovery | lihat docs/HASIL-105.md |
| 106 | recovery monitor: spawn probe pengganti bila ctx.probe mati (job terminal) + tes kedua rute (ABORTED/COMPLETED); INVENTARIS V7 | lihat docs/HASIL-106.md |
| 107 | item 13 TUTUP: perbaiki NameError deadline di rotate_source_ports + teruskan deadline (probe_dns, probe_all) + verify_udp_reflection (6 bagian, 40 cek) | lihat docs/HASIL-107.md |
| 108 | koreksi INVENTARIS item 13 (langkah STEP-107 yang gagal) + rekam permukaan item 10 dan jalankan probe_spoof langsung | lihat docs/HASIL-108.md |
| 109 | jalur raw spoof: IPLEN_ORDER sesuai platform (host order di BSD/macOS) + _local_ip() ganti gethostbyname(gethostname()) yang mengembalikan 127.0.0.1 | lihat docs/HASIL-109.md |
| 110 | spoof sumber terbukti jalan; penerima probe_spoof diganti UDP socket terikat sport (raw recv macOS buta) + perbaiki socket._local_ip() + 3 cek pengunci | lihat docs/HASIL-110.md |
| 111 | item 10 TUTUP: verify_dns_ownership (30 cek offline, txt_quorum di-monkeypatch) - quorum verify, endpoint verify/dns, ranting dns layer_attrib | lihat docs/HASIL-111.md |
| 112 | item 14 TUTUP: alive_all/wait_all_dead (hitung keturunan lewat pgrep) + verify_worm (cascade end-to-end, nol yatim sebelum reap) | lihat docs/HASIL-112.md |
- STEP-113 — item 9 TUTUP: mark_proven jadi metode; REGISTRY global dipulihkan (regresi patch). verifier 39 cek lulus, gate rc=0, test RESULTS: 82 passed, 0 failed, 1 skipped.
- STEP-114 — item 2/3 lane proxy + item 4 label multi-lane TUTUP: backend/proxy.py (direct default, rotasi opt-in, statistik per-lane terpisah), Transport._lane_endpoint + _label_lane, endpoint /lanes. verifier RESULTS: 48 passed, 0 failed, gate rc=0.
- STEP-115 — V4 run nyata Mode Aktif TUTUP: make demo DEMO_OK, down_verified=true, 4 transisi, ttr "time_to_recover": 44.373. PRD tuntas.
- STEP-120 — auth menyala tanpa mematikan UI/suite/verifier; gate 37 verifier hijau, 0 GAGAL; port ter-bind 127.0.0.1 + backup data.
- STEP-121 — segarkan dokumen handoff (SESSION_STATE/HANDOFF/RINGKASAN-AKHIR) ke keadaan pasca-STEP-120: PRD 33/0, live, auth, bukti pihak ketiga.
