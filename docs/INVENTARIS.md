# INVENTARIS PENDING — status terverifikasi

Diperbarui: STEP-55. Sumber: daftar INVENTARIS lama + cross-check terhadap repo.
Legenda: SELESAI | SEBAGIAN | PENDING | PERLU-VERIFIKASI

## A. Verifikasi
| # | Item | Status | Bukti |
|---|---|---|---|
| V1 | make test setelah semua hunk | SELESAI | 59 check hijau (naik dari 38) |
| V2 | Cakupan suite active/discovery/probes/auth/routeoverride/observer | SELESAI (via tests_integration) | 83 nama check(); semuanya melapor (lulus/lewat) |
| V6 | 3 check() tidak pernah dieksekusi | SELESAI (STEP-104) | 82 nama check() selalu melapor; dijaga check "semua nama check() melapor" |
| V7 | Recovery monitor bisa diverifikasi untuk job terminal (ABORTED) | SELESAI (STEP-106) | orchestrator: spawn probe pengganti bila ctx.probe MATI; kedua rute diuji di tests_integration |
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
| Item 10 DNS manipulation | SEBAGIAN | quorum TXT /targets/*/verify/dns + lapisan dns di layer_attrib.py + probe_spoof di udp_probe; belum ada verifier khusus |
| Item 13 UDP reflection | SEBAGIAN | backend/udp_probe.py (rasio amplifikasi, SSDP, reflection_capable) ter-wire di api.py:1378-1384; belum ada verifier khusus |
| Item 14 worm/lease | SEBAGIAN | backend/worker_daemon.py: lease fail-closed (LEASE_GRACE) + heartbeat + /workers/*/heartbeat; bagian sebar agent belum |
| Item 6/8/11/12 | SELESAI + teruji |
| GOAL 2 observer tersambung | SELESAI | tools/verify_goal2_wiring.py (20+ cek, hijau di make gate) |
| P1.4 kepemilikan dns_txt (rank 4) end-to-end | SELESAI | docs/HASIL-55.md + tools/verify_ownership_rung1.py |
| Item 6 audit dashboard | SELESAI | docs/UI-API-GAP.md (v4) + docs/DASHBOARD-AUDIT.md |
| GOAL 3 T1/T2 | SELESAI + teruji |

## D. Dokumen kontradiktif (belum tersentuh)
k6-worker/PRD-ADDENDUM-EDGE-CLIENT-SIM.md, k6-worker/READINESS-CHECKLIST.md,
README.md, docs/SESSION-HISTORY-COMPLETE.md, docs/WEBHOOK-API.md

## E. Tier
T1 SELESAI (8a RBAC, 8b MFA, 8c backup, 8d Docker) | T2-T3 SELESAI (9a NATS, 9b alerting, 9c OTLP, 9d PG); T4 belum dispesifikasi

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
| P0.1b | backend/ownership_ladder.default_fetcher() masih urllib.request.urlopen polos, bukan netssl.context() (temuan STEP-55) | TUTUP (STEP-74): context=_ns.context() di ownership_ladder/webhooks/worker_daemon/run_local; verifier memindai urlopen telanjang (E) + AST import level modul (E2); verify_devup.py menjaga run_local. |
| F-1 | flaky 409 pada dispatch job. SEBAB SEBENARNYA: /start fail-fast balas 409 bila preflight async belum PASS (api.py:845). DITUTUP STEP-60c/64-K: helper start_job toleran 409 (30x0.4s), berlaku untuk semua bentuk pemanggilan /start. | TUTUP |
| F-2 | UI memanggil GET /admin/secret & GET /healthz - TUTUP: keduanya path sisi-target, bukan route API (STEP-57) | TUTUP |
| F-3 | Tidak ada Content-Security-Policy pada respons API/dashboard (STEP-56) | TUTUP (STEP-76: CSP + nosniff + Referrer-Policy + X-Frame-Options pada dokumen; verify_headers 21/0.) |
| F-4 | CORS "*" digabung Bearer token (STEP-56) | TUTUP (STEP-76: GALARDO_CORS_ORIGINS + Vary: Origin + omit strict untuk origin tak terdaftar; preflight diuji.) |
| F-5 | UI tidak mengirim Authorization ke API - by design D14 (header absen = boleh) | BUKAN TEMUAN |
| F-6 | Gate STEP-58 tidak memuat verifier & node --check, sehingga commit lolos membawa JS rusak (sudah diperbaiki STEP-58b) | TUTUP |
| F-7 | Probe UDP (/sources/*/udp) melebihi timeout 15s -> suite crash. Tes kini timeout=45. Endpoint perlu ditinjau. | TUTUP (STEP-75): budget total (GALARDO_UDP_BUDGET, default 8s) + deadline ke loop fan-out + timeout per-target dibatasi + endpoint teruskan budget; verifier verify_udp_budget 16/0. |
| F-8 | /start balas 409 untuk preflight belum siap (fail-fast) - keputusan desain, bukan bug. | BUKAN TEMUAN |
| Item 8a RBAC | SELESAI | docs/HASIL-64.md |
| Item 8b MFA TOTP | SELESAI | docs/HASIL-65.md |
| Item 8c backup | SELESAI | docs/HASIL-66.md |
| Item 8d Docker Compose | SELESAI | docs/HASIL-67.md |
| Item 9b alerting | SELESAI | docs/HASIL-69.md |
| Item 9c OTLP export | SELESAI | docs/HASIL-70.md |
| Item 9d klien PG | SELESAI | docs/HASIL-71.md |
| F-9 | bus.publish di webhooks.fire() memakai variabel loop (hook/delivery_id) sehingga NATS tak menerima event saat tak ada hook berlangganan. DITUTUP STEP-69: fire() ditulis ulang. | TUTUP |
| F-10 | Kode sisipan memakai _m.group(1) padahal _match() mengembalikan LIST, bukan match object (AttributeError -> 500). DITUTUP STEP-69: helper _g1() tahan dua bentuk. | TUTUP |
| F-11 | /users/*/role menuntut ADMIN padahal aktor default TEST_OPERATOR -> ayam-telur, tak ada yang bisa ubah peran. DITUTUP STEP-69: syarat diturunkan ke TEST_OPERATOR. | TUTUP |
| F-12 | _g1() memanggil dirinya sendiri (regex ikut mengganti m.group(1) di dalam _g1); lolos karena _match selalu mengembalikan list. DITUTUP STEP-69. | TUTUP |
| F-13 | startup packet PG kurang byte terminator (\0) -> server menolak; verifier offline belum memeriksanya. DITUTUP STEP-71b: terminator ditambahkan + cek verifier. | TUTUP |
| F-14 | SCRAM client rusak di 5 titik: NUL pada SASLResponse, nonce klien dobel di client-final, AuthMessage salah bentuk (gs2 header ikut, server-first hilang), R/code 12 (SASLFinal) tak ditangani, tanda tangan server dihitung atas AuthMessage terpotong. DITUTUP STEP-71c: vektor RFC 7677 di verifier + uji live hijau. | TUTUP |
| F-1b | Kambuhan flake F-1 (dispatch 409, ~17%). Akar: start_job menulis REJECTED pada kegagalan preflight yang sebenarnya RETRYABLE (konflik sesaat) + state PREFLIGHT tak bisa distart ulang sehingga 60x retry sia-sia. DITUTUP STEP-97: konflik=retryable (tetap PENDING), cek mandatory lain tetap REJECTED, respons /start punya flag retryable, verifier verify_start_reject 9/9. | TUTUP (STEP-97) |
| F-15 | backend/rbac.py:45 memanggil db.all("users") padahal db.py tidak punya all(). AttributeError laten. DITUTUP STEP-72: alias all(name, filt=None) -> list(). | TUTUP |
| F-16 | Adapter db_pg salah membaca balikan query: pg.PG.query() mengembalikan (rows, err) dan tidak melempar, sehingga fail-open tidak pernah aktif dan hasil terbaca [rows, None]. Tak ada verifier yang menyentuh adapter. DITUTUP STEP-72: _rows() periksa err + lempar; fake-conn di verifier. | TUTUP |
| F-17 | db_pg.status() melaporkan _ready/_reason tanpa memicu koneksi -> panggilan pertama selalu mode json walau PG hidup. Ketangkap uji live, bukan verifier offline. DITUTUP STEP-72: status() memanggil active() + 2 cek regresi. | TUTUP |
| F-18 | Probe/e2e memakai path tanpa prefix /api/v1 -> 404 padahal server hidup; smoke.sh hanya menguji import, tak pernah HTTP. DITUTUP STEP-73: prefix benar dipakai, smoke.sh menambah uji HTTP sebelum ringkasan dan ikut rc. | TUTUP |
| F-19 | Image Docker tidak pernah menjalankan pip install dan requirements.txt tidak ada -> container crash-loop (ModuleNotFoundError: yaml). Akibat: bukti 'docker health 200' STEP-67 berasal dari server HOST. DITUTUP STEP-73: requirements.txt dari scan AST + Dockerfile memasangnya; probe setelah host dimatikan + docker inspect. | TUTUP |
| F-20 | api.serve()/lab_target.serve() bind literal 127.0.0.1 sehingga port publish mati dari host (000) walau container healthy. Patch pertama no-op (GALARDO_BIND hanya dipakai di port_free()). DITUTUP STEP-73: helper _bind_host(). | TUTUP |
| F-21 | f-string bersarang kutip ganda butuh Python 3.12; host & image 3.11 -> SyntaxError -> container crash-loop (restarts=10). DITUTUP STEP-73: kutip tunggal di ekspresi f-string. | TUTUP |
| F-22 | verify_knee_probe flaky (E2 cache) + 28 verifier di luar `make test`. DITUTUP STEP-80: E2 deterministik (cache diisi dulu, ambang relatif), measure_retry, dan target `make gate` yang menjalankan semua verifier. | TUTUP |
| F-23 | start_job memindahkan state ke PREFLIGHT lalu menulis REJECTED tanpa membedakan cek yang gagal; PREFLIGHT tidak startable. DITUTUP STEP-97 (lihat F-1b). | TUTUP (STEP-97) |
| F-24 | Uji MFA replay menghitung ulang kode TOTP sehingga bisa melewati batas step 30s (flake). Server sudah benar. DITUTUP STEP-97: kode di-cache untuk request replay + diagnostik code_sama. | TUTUP (STEP-97) |

## Z. Koreksi STEP-103
Status di atas dikoreksi dari kode + verifier, bukan dari dokumen lain. Yang benar-benar
PENDING: item 9 botnet IoT global, item 2/3 lane proxy, item 4 transport multi-lane,
V4 run nyata Mode Aktif, V6 4 check() tidak pernah dieksekusi. Item 10/13/14 naik ke
SEBAGIAN (kode ada, verifier khusus belum); GOAL 2 observer SELESAI. Seksi E dulu
bertentangan dengan tabel F di file ini sendiri.
