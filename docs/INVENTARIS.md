# INVENTARIS PENDING — status terverifikasi

Diperbarui: STEP-27. Sumber: daftar INVENTARIS lama + cross-check terhadap repo.
Legenda: SELESAI | SEBAGIAN | PENDING | PERLU-VERIFIKASI

## A. Verifikasi
| # | Item | Status | Bukti |
|---|---|---|---|
| V1 | make test setelah semua hunk | SELESAI | 59 check hijau (naik dari 38) |
| V2 | Cakupan suite active/discovery/probes/auth/routeoverride/observer | SEBAGIAN | ada di tests_integration.py, bukan target make terpisah |
| V3 | GALARDO_CF_TOKEN | SELESAI | .env + cf_check http=200 + zone active |
| V4 | Run nyata Mode Aktif pasca perubahan | PENDING | belum ada run sejak tier1 + Fase A |
| V5 | data/ | SELESAI | data/ dan logs/ dibuat |

## B. Defect
| ID | Status |
|---|---|
| D14 (api._auth header kosong) | SELESAI - terverifikasi membaca api.py |
| D11 (api._static os.sep) | PERLU-VERIFIKASI |
| D5 (worker_daemon k6 yatim) | PERLU-VERIFIKASI |
| D6 (last_control_ok saturasi) | PERLU-VERIFIKASI |
| D8 (webhook job.recovery/safety.abort) | PERLU-VERIFIKASI |
| D12 (3 sumber kebenaran port) | PERLU-VERIFIKASI |

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
