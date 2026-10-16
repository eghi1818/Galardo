# INVENTARIS PENDING — status terverifikasi

Diperbarui: STEP-27. Sumber: daftar INVENTARIS lama + cross-check terhadap repo.
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
| Item 5 T3 edge rule | SEBAGIAN (koler.space active; bukti end-to-end belum) |
| Item 2/3 lane proxy | PENDING (proxy.py tidak ada; transport sudah punya proxy) |
| Item 4 transport multi-lane | PENDING |
| Item 9 botnet IoT global | PENDING |
| Item 10 DNS manipulation | PENDING |
| Item 13 UDP reflection | PENDING |
| Item 14 worm/lease | PENDING |
| Item 6/8/11/12 | SELESAI + teruji |
| GOAL 2 observer tersambung | PENDING |
| GOAL 3 T1/T2 | SELESAI + teruji |

## D. Dokumen kontradiktif (belum tersentuh)
k6-worker/PRD-ADDENDUM-EDGE-CLIENT-SIM.md, k6-worker/READINESS-CHECKLIST.md,
README.md, docs/SESSION-HISTORY-COMPLETE.md, docs/WEBHOOK-API.md

## E. Tier
T1 SEBAGIAN (Ed25519 selesai; RBAC+MFA, backup, Docker pending) | T2-T4 PENDING

## F. Aturan anti-overlap
- SEBELUM mengerjakan item apa pun, cek file ini dulu.
- Item berstatus SELESAI tidak dikerjakan ulang kecuali ada bukti regresi.
- Kalau status di sini bertentangan dengan dokumen lain, file ini yang menang
  untuk soal STATUS; docs/CONTEXT.md menang untuk soal ATURAN.
