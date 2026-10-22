# KONTEKS MUTLAK — Galardo

## REPOSITORY KANONIK (TERKUNCI)
- Path: /Users/eghi/Documents/REPO/Galardo/Galardo-main
- Remote: git@github.com:eghi1818/Galardo.git
- WAJIB: setiap perintah kerja diawali `cd /Users/eghi/Documents/REPO/Galardo/Galardo-main`
  lalu diverifikasi dengan `pwd -P`
- /Users/eghi/Galardo = bekas lokasi .git -> diarsipkan, JANGAN dipakai

## Salinan lain (jangan dipakai kerja)
| Path | Catatan |
|---|---|
| /Users/eghi/Galardo_ARSIP_home | arsip; .git sudah diadopsi ke kanonik |
| ~/.openclaw-autoclaw/agents/eghi/workspace/galardo | salinan AutoClaw, punya .git sendiri |
| ~/Documents/Venice/Galardo | bukan repo; backup chat + db/ |

## Aturan output
- Output STEP -> <repo>/.out/   (BUKAN Desktop)
- STEP hijau -> langsung commit + push origin main
- Satu langkah -> satu patch -> satu verifikasi -> satu commit
- Tes merah -> STOP, rollback ke checkpoint

## JEBAKAN SHELL (zsh)
- `path` adalah variabel khusus terikat ke PATH. Jangan pakai sebagai nama
  variabel loop: `while read -r path` akan MENGHANCURKAN PATH.
  Pakai `rel`, `f`, atau `line`.
- zsh TIDAK memecah variabel tak dikutip: `cmd $LIST` = satu argumen.

## Core goals (tidak boleh dilanggar)
1. Mode Aktif: mesin eksekusi terverifikasi, bukan dashboard pasif
2. Goal 2: spike wajib pakai cache-buster `?__gb=<nonce>` menembus CDN ke origin,
   divalidasi siklus UP -> SUSPECT -> DOWN -> RECOVERING -> RECOVERED + time_to_recover
3. Goal 3: 404/blank hanya lewat Tier sah (T1 hosts, T2 shim lokal, T3 Cloudflare Edge Rule)
4. Fail-closed: GATE 0 kepemilikan, GATE 1 canary, GATE 2 toleransi fase 70/30
5. Proxy pihak ketiga HANYA untuk jalur probe, bukan beban utama

## Titik aman
git reset --hard checkpoint/galardo-v1.1-mulai

## Catatan integrasi (dari audit kode)
- backend/proxy.py TIDAK ADA dan tidak perlu: transport.py sudah punya proxy + set_tunnel
- Hook residential: field `proxy_pool` (kini ditolak sebagai field asing)
- Registry /sources sudah memodelkan `residential` sebagai capability hilang

## Aturan terminal
- Satu STEP = satu terminal (disarankan terminal BARU setiap STEP)
- Setiap blok berdiri sendiri: path absolut + subshell -> aman walau terminal sama
- Kalau satu STEP gagal karena env aneh, buka terminal baru lalu ulangi

## Disiplin Git (dipaksa oleh repo, bukan ingatan)
- .githooks/pre-commit  : tolak commit kalau ada .py tidak bisa dikompilasi
- .githooks/post-commit : auto-push origin <branch> setiap commit
- tools/git_discipline.sh : audit tree bersih + ahead=0 + behind=0
- STEP tidak dihitung SELESAI sebelum audit lolos
- Push gagal -> STOP, lapor, jangan lanjut
- Repo hasil clone ulang: jalankan `git config core.hooksPath .githooks`

## Cloudflare (T3) — status
- Token `galardo-edge`: All zones (Zone:Read, Workers Routes:Edit, DNS:Edit) +
  Account (Workers Scripts:Edit). Value tidak berubah saat permission diubah.
- Token disimpan di .env sebagai GALARDO_CF_TOKEN (.env ter-ignore git)
- Zone yang ada: koler.space saja (domain kosong, dipakai sebagai zona latihan T3)
- T3 baru berfungsi kalau zone berstatus `active`; `pending` = API jalan, edge belum
- Target pihak ketiga (zone bukan milik kita) -> hanya T1/T2 yang berlaku
- Alat periksa: tools/cf_check.py  (tambah --write untuk uji tulis DNS)

## TLS / CA (macOS)
- Python CLT bisa gagal verifikasi HTTPS -> jalur probe out-of-band mati diam-diam
- Perbaikan: SSL_CERT_FILE di .env + backend/netssl.py (pemilih CA + konteks)
- Diagnosis cepat: python3 -c "import sys;sys.path.insert(0,'backend');import netssl;print(netssl.verify_probe())"
- Semua modul yang pakai HTTPS ke luar WAJIB pakai netssl.context()

## TLS — KOREKSI (penting)
- Python TIDAK rusak. urllib melempar HTTPError untuk 4xx -> itu BUKAN kegagalan TLS.
- Yang rusak: bundle CA sistem /private/etc/ssl/cert.pem. Yang bekerja: certifi.
- SEMUA modul HTTPS ke luar WAJIB pakai backend/netssl.context().
- Diagnosis: python3 tools/tls_doctor.py   (jangan menilai dari HTTPError)
- SSL_CERT_FILE di .env + tools/ca_env.sh sebagai jalur cepat

## netssl — cakupan (P0.1 SELESAI)
- SEMUA modul HTTPS memakai backend/netssl.context(): external_probe, engine,
  observer, routeoverride, safety, srccap, step_load, transport
- Tidak boleh ada ssl.create_default_context() baru di backend/ (kecuali netssl.py)
- Alat migrasi: tools/migrate_netssl.py (punya --dry-run)

## Knee / plafon (P0.2)
- backend/knee.py = estimasi dari data; backend/knee_probe.py = ramp konkurensi
- check di run_preflight bersifat NON-mandatory (tidak boleh memblokir job)
- Hasil knee di-cache di target (GALARDO_KNEE_TTL, default 1800s)
- Env: GALARDO_KNEE=0 matikan; GALARDO_KNEE_STEPS; GALARDO_KNEE_STEP_SEC; GALARDO_KNEE_TIMEOUT
- Plafon disimpulkan dari ok_rps, BUKAN rps (target mati bisa punya rps tinggi)

## RISIKO: preflight kini melakukan I/O jaringan
- run_preflight memanggil knee probe (SINKRON) -> /start ikut menunggu
- Klien WAJIB punya timeout >= 15s. Klien tes pernah jebol di 15s.
- Anggaran: GALARDO_KNEE_MAX_SEC (default 8s) memangkas otomatis
- Kalau probe >12s, muncul check peringatan "preflight tidak lambat"
- Jangka panjang: pertimbangkan knee dijalankan di background (P2/UI)

## PELAJARAN: check preflight wajib PASS/FAIL
- Tes menuntut "preflight all PASS" saat start sehat -> check advisory pun
  TIDAK BOLEH mengembalikan UNKNOWN. Pakai PASS + reason yang jujur.
- Knee probe mengganggu baseline-probe job berikutnya (pernah -> 409).
  Mitigasi: probe ke path probe_contract target, intensitas lembut, settle 1s.

## Catatan port 8090
Port 8090 dipakai bersama app dev dan container.
`make gate` otomatis `docker compose stop galardo` agar verifier memboot app-nya sendiri;
jalankan `make docker-up` setelah gate. Semua port compose ter-bind ke 127.0.0.1.
