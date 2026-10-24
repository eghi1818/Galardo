# STATUS SEKARANG — Galardo (otomatis STEP-136)

- waktu  : 2026-10-24 09:51
- HEAD   : 11c2903 fix(verify): data dir terpisah untuk app verifier; docs: diagnosa gate rc=2
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, termasuk seksi 9 MODE B)

## Status komponen
- MESIN PENGGUNA: SELESAI dan terkunci (verify_auth_users 20 cek hijau, rc=0)
- make test: rc=0 (82 passed / 0 failed / 1 skipped)
- make gate: rc=2  <-- satu-satunya yang belum hijau
  - gejalanya: gate berhenti SEBELUM daftar verifier (log gate tidak memuat baris verifier)
  - dugaan terkuat: langkah docker/compose di target gate; daemon OrbStack di mesin ini pernah mati
  - kalau docker sudah hidup dan gate masih merah: baca .out/STEP-136-gate.txt baris terakhir

## Pelajaran wajib (jangan diulang)
1. status 0 dari probe = exception, BUKAN sukses -> selalu '200 <= s < 400'
2. probe(method, path, body, cookie, ...) - body SEBELUM cookie
3. jalur cadangan jangan menyaring status: 'non-403', bukan '200..399' (422 harus lolos)
4. verifier pakai app + data dir miliknya sendiri (.out/vfy-data); port dibaca dari log sendiri
5. sesi hidup di MEMORI (data/sessions.json cuma flush) -> dua proses app = sesi saling menimpa
6. anchor patch bisa MISS tanpa error; selalu verifikasi dengan grep sesudah patch
7. jangan sebut selesai tanpa keluaran nyata; kalau merah tulis merah

## Cara menjalankan
- app  : nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- port : API 8090 (lab target 8095/8096 - deteksi lewat /api/v1/health)
- token: GALARDO_DEV_TOKEN (.env, Bearer) = master; admin usr-eghi/SUPERADMIN; verifier vfy-admin/verifikasi-123

## Urutan berikutnya (doktrin)
1. hijaukan gate (docker/OrbStack) -> lalu
2. backend/gateway.py + wiring Mode B (sticky per worker, catat IP egress per worker)
3. bukti rotasi egress nyata (butuh GALARDO_GATEWAY_URL)
4. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
5. ingest intel REA + pre-flight validasi
6. halaman Override (Goal 3)
7. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
8. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
