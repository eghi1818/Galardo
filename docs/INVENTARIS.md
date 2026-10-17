# INVENTARIS PENDING — status terverifikasi

Diperbarui: STEP-55. Sumber: daftar INVENTARIS lama + cross-check terhadap repo.
Legenda: SELESAI | SEBAGIAN | PENDING | PERLU-VERIFIKASI

## A. Verifikasi
| # | Item | Status | Bukti |
|---|---|---|---|
| V1 | make test setelah semua hunk | SELESAI | 59 check hijau (naik dari 38) |
| V2 | Cakupan suite active/discovery/probes/auth/routeoverride/observer | SELESAI (via tests_integration) | 63 check() terdaftar; 59 dieksekusi |
| V6 | 4 check() tidak pernah dieksekusi | PENDING | 63 terdaftar vs 59 dilaporkan |
| V3 | GALARDO_CF_TOKEN | SELESAI | .env + cf_check http=200 + zone active |
| V4 | Run nyata Mode Aktif pasca perubahan | PENDING | belum ada run sejak tier1 + Fase A |
| V5 | data/ | SELESAI | data/ dan logs/ dibuat |

## B. Defect - SEMUA SELESAI (terverifikasi STEP-28, ada bukti baris kode)
| ID | Status | Bukti |
|---|---|---|
| D14 | SELESAI | api.py:182-190 - absen lolos, kosong ditolak |
| D11 | SELESAI | api.py:303-309 - normpath + root + os.sep |
| D5 | SELESAI | worker_daemon.py:168,210,211 - wait(timeout) + TimeoutExpired |
| D6 | SELESAI | worker_daemon.py:138,156 - lease refresh + LEASE_GRACE |
| D8 | SELESAI | orchestrator.py:109 (job.recovery), :529 (safety.abort) |
| D12 | SELESAI | run_local.py scan port bebas, dipakai seragam; .env.example + Makefile |

## C. Fitur Goals
| Item | Status |
|---|---|
| Item 1 cache-buster | SELESAI (cachebuster.py + engine + step_load, penanda __gb) |
| Item 5 T3 edge rule | SELESAI | bukti live .out/HASIL-48.md + docs/T3-RUN.md (404 + blank via edge, revert bersih) |
| Item 2/3 lane proxy | PENDING (proxy.py tidak ada; transport sudah punya proxy) |
| Item 4 transport multi-lane | PENDING |
| Item 9 botnet IoT global | PENDING |
| Item 10 DNS manipulation | PENDING |
| Item 13 UDP reflection | PENDING |
| Item 14 worm/lease | PENDING |
| Item 6/8/11/12 | SELESAI + teruji |
| GOAL 2 observer tersambung | PENDING |
| P1.4 kepemilikan dns_txt (rank 4) end-to-end | SELESAI | docs/HASIL-55.md + tools/verify_ownership_rung1.py |
| Item 6 audit dashboard | SELESAI | docs/UI-API-GAP.md (v4) + docs/DASHBOARD-AUDIT.md |
| GOAL 3 T1/T2 | SELESAI + teruji |

## D. Dokumen kontradiktif (belum tersentuh)
k6-worker/PRD-ADDENDUM-EDGE-CLIENT-SIM.md, k6-worker/READINESS-CHECKLIST.md,
README.md, docs/SESSION-HISTORY-COMPLETE.md, docs/WEBHOOK-API.md

## E. Tier
T1 SEBAGIAN (Ed25519 selesai; RBAC+MFA, backup, Docker pending) | T2-T4 PENDING

## E2. Risiko terbuka
| Risiko | Status | Catatan |
|---|---|---|
| Preflight sinkron ber-I/O -> /start menunggu | DIMITIGASI | anggaran GALARDO_KNEE_MAX_SEC; pertimbangkan async |
| make test melambat karena knee per job | DIMITIGASI | TTL cache di target |

## F. Aturan anti-overlap
- SEBELUM mengerjakan item apa pun, cek file ini dulu.
- Item berstatus SELESAI tidak dikerjakan ulang kecuali ada bukti regresi.
- Kalau status di sini bertentangan dengan dokumen lain, file ini yang menang
  untuk soal STATUS; docs/CONTEXT.md menang untuk soal ATURAN.
## G. Temuan tercatat (belum dikerjakan)
| ID | Temuan | Status |
|---|---|---|
| P0.1b | backend/ownership_ladder.default_fetcher() masih urllib.request.urlopen polos, bukan netssl.context() (temuan STEP-55) | BELUM |
| F-1 | flaky 409 pada dispatch job. SEBAB SEBENARNYA: /start fail-fast balas 409 bila preflight async belum PASS (api.py:845). DITUTUP STEP-60c/64-K: helper start_job toleran 409 (30x0.4s), berlaku untuk semua bentuk pemanggilan /start. | TUTUP |
| F-2 | UI memanggil GET /admin/secret & GET /healthz - TUTUP: keduanya path sisi-target, bukan route API (STEP-57) | TUTUP |
| F-3 | Tidak ada Content-Security-Policy pada respons API/dashboard (STEP-56) | TERBUKA |
| F-4 | CORS "*" digabung Bearer token (STEP-56) | TERBUKA |
| F-5 | UI tidak mengirim Authorization ke API - by design D14 (header absen = boleh) | BUKAN TEMUAN |
| F-6 | Gate STEP-58 tidak memuat verifier & node --check, sehingga commit lolos membawa JS rusak (sudah diperbaiki STEP-58b) | TUTUP |
| F-7 | Probe UDP (/sources/*/udp) melebihi timeout 15s -> suite crash. Tes kini timeout=45. Endpoint perlu ditinjau. | TERBUKA |
| F-8 | /start balas 409 untuk preflight belum siap (fail-fast) - keputusan desain, bukan bug. | BUKAN TEMUAN |
