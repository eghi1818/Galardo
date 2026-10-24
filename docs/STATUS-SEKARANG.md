# STATUS SEKARANG — Galardo (otomatis STEP-137)

- waktu  : 2026-10-24 10:01
- HEAD   : 92e28c4 fix(verify): matikan pkill default (jangan bunuh app verifier lain); docs: gate merah = verify_headers
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, termasuk seksi 9 MODE B)

## Status komponen
- MESIN PENGGUNA: SELESAI (verify_auth_users 20 cek hijau, rc=0, dan ok di dalam gate)
- make test: rc=0 (82 passed / 0 failed / 1 skipped)
- make gate: rc=2  <-- MERAH di SATU verifier: verify_headers.py (41 verifier lain ok)
  - BUKAN docker (docker SIAP). Koreksi ini penting: HASIL-136 salah menyebut docker.
  - tersangka utama: pkill di verifier auth membunuh app verifier lain -> default sudah diubah ke 0
  - bukti: .out/STEP-137-headers.txt (keluaran langsung verify_headers.py)
  - flaky lain: tests_integration baris 439 (POST /targets/tgt-lab/verify/dns) pernah socket.timeout

## Pelajaran wajib (jangan diulang)
1. status 0 dari probe = exception, BUKAN sukses -> selalu '200 <= s < 400'
2. probe(method, path, body, cookie, ...) - body SEBELUM cookie
3. jalur cadangan jangan menyaring status: 'non-403', bukan '200..399' (422 harus lolos)
4. verifier pakai port app sendiri (dibaca dari log sendiri)
5. sesi hidup di MEMORI -> dua proses app = sesi saling menimpa; login ulang menyelesaikan
6. jangan pkill app milik verifier lain kalau gate bisa paralel
7. anchor patch bisa MISS tanpa error; verifikasi dengan grep sesudah patch
8. jangan sebut selesai tanpa keluaran nyata; kalau merah tulis merah

## Cara menjalankan
- app  : nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- port : API 8090 (lab target 8095/8096 - deteksi lewat /api/v1/health)
- token: GALARDO_DEV_TOKEN (.env, Bearer) = master; admin usr-eghi/SUPERADMIN

## Urutan berikutnya
1. hijaukan verify_headers (lihat .out/STEP-137-headers.txt) -> gate hijau
2. backend/gateway.py + wiring Mode B (sticky per worker, catat IP egress per worker)
3. bukti rotasi egress nyata (butuh GALARDO_GATEWAY_URL)
4. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
5. ingest intel REA + pre-flight validasi
6. halaman Override (Goal 3)
7. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
8. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
