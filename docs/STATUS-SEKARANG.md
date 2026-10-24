# STATUS SEKARANG — Galardo (otomatis STEP-138)

- waktu  : 2026-10-24 10:11
- HEAD   : 02a6834 fix(api): preflight OPTIONS 204 di mode CORS ketat (eksperimen pembungkus do_*)
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, seksi 9 MODE B)

## Status komponen
- MESIN PENGGUNA: SELESAI (auth 20 cek hijau, ok di gate)
- make test: rc=0
- verify_headers: rc dengan pembungkus=1 | tanpa pembungkus=1  <-- cek A 'preflight OPTIONS balas 204'
- make gate: rc=2
  - bila masih merah: SATU-SATUNYA verifier merah = verify_headers.py cek A preflight 204
  - detail: mode CORS ketat (GALARDO_CORS_ORIGINS) + Origin tak terdaftar harus tetap 204
  - bukti: .out/STEP-138-h1.txt, .out/STEP-138-h2.txt, .out/STEP-138-cors.log

## Pelajaran wajib (jangan diulang)
1. status 0 dari probe = exception, BUKAN sukses -> '200 <= s < 400'
2. probe(method, path, body, cookie, ...) - body SEBELUM cookie
3. jalur cadangan jangan menyaring status: 'non-403', bukan '200..399'
4. verifier pakai port app sendiri; jangan pkill app verifier lain
5. sesi hidup di MEMORI -> dua proses app = sesi saling menimpa
6. anchor patch bisa MISS tanpa error; verifikasi dengan grep
7. jangan sebut selesai tanpa keluaran nyata; kalau merah tulis merah
8. JANGAN sebar hipotesis sebagai fakta: 'gate merah karena docker' sudah terbukti SALAH

## Urutan berikutnya
1. hijaukan verify_headers cek A preflight 204 -> gate hijau
2. backend/gateway.py + wiring Mode B (sticky per worker, catat IP egress per worker)
3. bukti rotasi egress nyata (butuh GALARDO_GATEWAY_URL)
4. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
5. ingest intel REA + pre-flight validasi
6. halaman Override (Goal 3)
7. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
8. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
