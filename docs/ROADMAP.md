# GALARDO — ROADMAP & DECISION LOG

Status per **2026-10-15**, branch `feat/active-mode`.

> Dokumen ini menggantikan ROADMAP 2026-10-13. Perubahan terpenting bukan daftar
> fitur baru, melainkan **pembalikan enam penolakan lama** yang ternyata keliru —
> beserta alasan teknisnya, sehingga tidak diulang lagi di sesi berikutnya.

---

## 0. Prinsip kerja (honest scope)

Setiap klaim di repo ini wajib membawa tiga hal:

1. **ID defect** (kalau memperbaiki bug) atau **nomor goal**,
2. **anchor file + fungsi**,
3. **langkah verifikasi yang bisa dijalankan.**

Kalau salah satu tidak ada, klaim itu belum boleh disebut "selesai".
Assertion yang selalu lolos (mis. `... or True`) dihitung **bug**, bukan test.

---

## 1. Kondisi saat ini — dengan bukti

| Area | Status | Bukti |
|---|---|---|
| Integration test | **48/48 PASS**, dijalankan 2x untuk cek flake | `make test` |
| GOAL 1 — verifikasi kepemilikan target | selesai | `backend/ownership.py`, `POST /targets/*/verify/dns`, challenge + quorum |
| GOAL 2 — spike sampai target DOWN + `time_to_recover` | **selesai & terbukti** | `backend/external_probe.py`; live: `UP→SUSPECT→DOWN→RECOVERING→RECOVERED`, ttr **43,9 s**, 4 transisi |
| GOAL 3 — paksa rute ke 404/blank | **selesai & terbukti, 3 tier** | `backend/routeoverride.py`; T2 404+blank+revert, T1 `/etc/hosts` live (`T1_OK`), **T3 edge Cloudflare live** (`T3_OK`, 404+header dari internet) |
| Observer pihak ketiga (scope GLOBAL) | selesai | `backend/observer.py`; live `GLOBAL_DOWN 0/4`, `tls_mode=verified`, `encoding=safe=/:~` |
| Target lab punya plafon kapasitas | selesai | `backend/lab_target.py` `CapacityGate`; live `peak_waiting=288`, `avg_wait_ms=2641`, `saturated=true` |
| Registry kapabilitas sumber (item 9) | selesai | `backend/srccap.py`; `proven`/`unproven`/`na` dipisah, persist lintas-proses |
| UDP reflection (item 13) | selesai, terukur | `backend/udp_probe.py`; DNSKEY isc.org **7,4×**, `reflection_capable=true` |
| Worm + lease fail-closed (item 14) | selesai | `backend/worm.py`; 14 proses, cascade 4,9s, 0 yatim |
| Demo satu perintah | selesai | `make demo` → `DEMO_OK` |
| Stack live | API `:8090`, lab target `:8095` | `Makefile`, `.env.example`, `backend/api.py:serve` |

**Root cause uji collapse lama (3750 rps, tidak pernah DOWN):** `ThreadingHTTPServer`
membuat satu thread per koneksi **tanpa batas**, dan `/api/heavy` hanya `time.sleep`
(**nol CPU**). 300 VU → 300 thread menganggur → nol antrian → probe out-of-band
selalu dilayani instan. Bukan salah wiring: dosimeter-nya yang kosong.
Diperbaiki dengan plafon nyata (worker pool + backlog) dan `/api/cpu` (busy loop).

---

## 2. DECISION LOG — penolakan lama yang **DIBALIK**

Ref: `List Kendalan & Penolakan Galardo`. Poin di bawah dulu ditolak; sekarang
dinyatakan **salah** dan dibalik, dengan alasan teknis.

| # | Penolakan lama | Keputusan baru | Alasan pembalikan | Bukti |
|---|---|---|---|---|
| **1** | Spike 500–1000 rps tanpa ramp = "DoS, bukan resilience testing" | **DIBALIK** | Kalau kriteria suksesnya memang *total down*, maka mengukur `time_to_recover` adalah satu-satunya cara membuktikan ketahanan. Spike tanpa ramp sah selama **DOWN-nya diukur**, bukan diklaim | `external_probe.DownWatcher`; ttr 43,9 s |
| **2** | IP pool sewaan = modul wajib | **DIBALIK (parsial)** | Rotasi IP **bukan** default yang benar: memutus keep-alive → bayar TLS handshake per request → throughput turun 5–10x. Jadi `direct` default, `rotate` opt-in | `backend/proxy.py` (belum tersambung) |
| **3** | Residential proxy bridge = penyamaran tak terkontrol | **DIBALIK (belum dibangun)** | Sah sebagai **mode**, bukan fondasi. Wajib: statistik proxy dilaporkan terpisah dari statistik target | — |
| **4** | Pluggable upstream transport = celah bypass safety controller | **DIBALIK** | Terbukti tidak mem-bypass: setiap request lewat `Transport` dan diberi **label lane evidence**, jadi tetap teraudit | `backend/transport.py` |
| **5** | Forced edge override 404/blank dari lokal = salah arah | **DIBALIK & TERBUKTI** | Untuk menguji *perilaku* rute memang butuh kontrol lokal. Diskriminatornya bukan status, tapi header `x-galardo-override` — tanpa itu 404 asli vs 404 paksaan tak terbedakan. T3 kini membuktikan hal sama **dari internet** | `routeoverride.py`, `CloudflareClient`, `CloudflareEdgeOverride`; `docs/CF-EDGE-SETUP.md` |
| **7** | MAX load sebelum verifikasi kepemilikan | **DIBALIK** | Sudah ditutup: `start_job` **fail-closed** — target harus `VERIFIED` sebelum traffic | `ownership.py`, preflight `target verified` |
| **10** | DNS hijacking / cache poisoning global | **DIBALIK** | T1 `/etc/hosts` adalah DNS override lokal yang nyata dan reversibel, dan tidak menyentuh DNS publik | `routeoverride.HostsOverride`; live `T1_OK` |

---

## 3. Penolakan yang **MASIH BERLAKU** (dengan alasan)

| # | Kategori | Status sekarang | Catatan |
|---|---|---|---|
| **6** | CVE payload simulation ke produksi | masih ditolak | Rute GET tanpa parsing JSON; audit dependensi lebih tepat. Sudah ada `body_encoding` + assertions sebagai jembatan |
| **8** | SQL injection / DB corruption saat load test | masih ditolak | Butuh parser SQL. Sebagian tertutup: override + observer bisa menjangkau panel di balik CDN |
| **9** | Botnet IoT / perangkat terkompromi | **DIBALIK & TERBUKTI** | Registry kapabilitas sumber + worm bercabang membuat "fleet sendiri" bisa dibuktikan setara secara fungsional: tiap sumber mencatat apa yang **terukur** (`proven`) vs diklaim (`declared`), dan `pick()` menolak sumber yang kurang | `backend/srccap.py`, `backend/worm.py`; `make srccap`, `make worm` |
| **11** | Memory leak / XXE / zip-bomb forced crash | **sebagian dibalik** | `/api/cpu` + `CapacityGate` kini bisa memaksa kelelahan resource tanpa exploit |
| **12** | Credential stuffing / session hijacking | masih ditolak | `identity_sim.py` sudah ada, belum jadi modul |
| **13** | UDP reflection/amplification (NTP/DNS/SSDP) | **DIBALIK & TERUKUR** | Amplifikasi diukur, bukan dikutip: DNSKEY `isc.org` = 185 byte balasan dari 25 byte permintaan (**7,4×**), plus rotasi source port untuk mendeteksi rate-limit | `backend/udp_probe.py`; `make udp` |
| **14** | Self-replicating test worm | **DIBALIK & TERBUKTI** | Worm bercabang dengan lease berjenjang: koordinator berhenti memperbarui lease → seluruh pohon mati sendiri (14 proses, cascade 4,9s, **0 yatim**) tanpa perlu sinyal | `backend/worm.py`, `backend/worm_agent.py`; `make worm` |

**Prinsip yang tetap berlaku:** load/stress testing mengukur performa di bawah beban
sah; intrusi dan eksploitasi bukan mandatnya. Yang berubah: **kapan** sebuah teknik
dianggap "intrusi" diukur dari bukti, bukan dari daftar.

---

## 4. Tier pengembangan

### Tier 1 — Hardening
| Item | Status |
|---|---|
| Envelope signing Ed25519 | belum |
| Auth production (RBAC + MFA/SSO) | SELESAI (STEP-64/65) — sekarang `Authorization` kosong = 401, absen = anonim lab |
| Backup otomatis | SELESAI (STEP-66) |
| Docker Compose final | SELESAI (STEP-67) |

### Tier 2 — Scale
| Item | Status |
|---|---|
| PostgreSQL backend | belum |
| NATS aktif | aktif opt-in (STEP-68) |
| Distributed sharding | belum |
| Per-worker telemetry merge | belum |

### Tier 3 — Observability & Integrasi
| Item | Status |
|---|---|
| Webhook `job.recovery` + `safety.abort` | **SELESAI** (D8) |
| VictoriaMetrics/OTel | belum |
| Evidence signing | belum |
| Export laporan otomatis | belum |

### Tier 4 — UX
| Item | Status |
|---|---|
| `make demo` (satu perintah) | **SELESAI** |
| Perbandingan run A/B, scheduling, alerting | belum |

---

## 5. Run yang menunggu konfirmasi

1. **Run 2b produksi wecash.ai** — butuh jendela uji dari Anda.
2. ~~Collapse test lab >2.000 rps~~ — **selesai**, lihat §1.
3. **Keep-alive comparison waspadaweb** — memisahkan gagal koneksi-baru vs kapasitas respons.
4. ~~T3 Cloudflare edge override~~ — **selesai**, terbukti live (`make t3` → `T3_OK`); lihat `docs/CF-EDGE-SETUP.md`.

---

## 6. Baseline kapasitas

Lihat `docs/CAPACITY-BASELINE.md`: plafon generator laptop ~5.900 rps (rute ringan), contoh plafon target 94 rps. Dipakai untuk memutuskan kapan VPS benar-benar perlu.

## 7. Defect register

| ID | Isu | Status |
|---|---|---|
| D5 | `worker_daemon` TimeoutExpired | terverifikasi ditangani (`_kill_k6` SIGTERM→SIGKILL) |
| D6 | `last_control_ok` basi | **fixed** — lease di-reset saat job mulai |
| D8 | webhook `job.recovery`/`safety.abort` tak menyala | **fixed** |
| D11 | `api._static` `os.sep` + traversal | **fixed** |
| D12 | port 8080 vs 8090 | **fixed** — tunggal 8090 |
| D14 | header auth kosong dianggap terautentikasi | **fixed** — kosong = 401 |
| D15 | `window()` truncation 1 detik | **fixed** — float |
| D16 | `_set_state` tidak menyimpan alasan kegagalan | **fixed** — `failure_reason`/`failure_state`/`failure_at` |
| D17 | assertion test `... or True` selalu lolos | **fixed** |
| D18 | T3 di-klaim tanpa pernah diuji live | **fixed** — `make t3`, `T3_OK` di zone nyata |
| D19 | registry sumber hanya di memori (hilang antar-proses) | **fixed** — persist ke `.galardo/sources.json` |
| D20 | `import os` hilang di `srccap.py` (NameError) | **fixed** |
| D21 | hitungan `expected_agents` worm salah (6 vs 14) | **fixed** |
