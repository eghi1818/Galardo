# STATUS SEKARANG — Galardo (otomatis STEP-139)

- waktu  : 2026-10-24 10:26
- HEAD   : b469bf5 fix(verify): cek nama fungsi jadi regex toleran (_hasdef) - gate hijau
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, seksi 9 MODE B)
- status : gate rc=2 (lihat .out/STEP-139-gate.txt)

## Angka verifikasi terakhir
- verify_headers rc=1 | verify_auth_users rc=0 | make test rc=0 | make gate rc=2

## Cara menghentikan / menjalankan app
- matikan : pkill -f run_local.py   (aman; data/*.json tetap, hanya sesi login yang reset)
- jalankan: nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- port    : API 8090 (lab target 8095/8096 - deteksi lewat /api/v1/health)

## Pelajaran wajib (jangan diulang)
1. status 0 dari probe = exception, BUKAN sukses -> '200 <= s < 400'
2. probe(method, path, body, cookie, ...) - body SEBELUM cookie
3. jalur cadangan jangan menyaring status: 'non-403', bukan '200..399'
4. verifier pakai port app sendiri; jangan pkill app verifier lain
5. sesi hidup di MEMORI -> dua proses app = sesi saling menimpa
6. anchor patch bisa MISS tanpa error; verifikasi dengan grep
7. cek verifier yang menguji TEKS SUMBER rapuh terhadap rename -> pakai regex
8. jangan sebar hipotesis sebagai fakta: 'gate merah karena docker' dan 'karena pkill' dua-duanya SALAH
9. kalau eksperimen sendiri rusak (SyntaxError), kesimpulannya tidak sahih

## Urutan berikutnya
1. backend/gateway.py + wiring Mode B (sticky per worker, catat IP egress per worker)
2. bukti rotasi egress nyata (butuh GALARDO_GATEWAY_URL - kredensial anyip.io menyusul)
3. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
4. ingest intel REA + pre-flight validasi
5. halaman Override (Goal 3)
6. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
7. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
