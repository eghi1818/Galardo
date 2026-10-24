# STATUS SEKARANG — Galardo (otomatis STEP-142)

- waktu  : 2026-10-24 11:41
- HEAD   : 27a14bf docs(STATUS): pondasi Mode B tercatat
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, seksi 9 MODE B)

## Pondasi
- SELESAI & terkunci: doktrin GOAL; mesin pengguna (auth 20 cek); gateway Mode B (verify_gateway 27 cek)
- endpoint /api/v1/gateway/status: 200 (200 = hidup)
- angka terakhir: gateway rc=0 | egress rc=0 (SKIP tanpa kredensial) | test rc=2 | gate rc=2

## Cara jalankan / hentikan app
- jalankan: nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- matikan : pkill -f run_local.py
- port    : API 8090 (lab target 8095/8096 - deteksi lewat /api/v1/health)

## Pelajaran wajib (jangan diulang)
1. status 0 dari probe = exception, BUKAN sukses -> '200 <= s < 400'
2. probe(method, path, body, cookie, ...) - body SEBELUM cookie
3. jalur cadangan jangan menyaring status: 'non-403', bukan '200..399'
4. verifier pakai port app sendiri; jangan pkill app verifier lain
5. sesi hidup di MEMORI -> dua proses app = sesi saling menimpa
6. anchor patch bisa MISS tanpa error; verifikasi dengan grep
7. cek verifier atas TEKS SUMBER rapuh terhadap rename -> pakai regex
8. guard penyisipan harus diuji (jangan pakai split yang sudah memuat penanda)
9. hipotesis bukan fakta ('gate merah karena docker'/'pkill' dua-duanya SALAH)
10. Mode B: rotasi per KONEKSI/WORKER, bukan per request; penentu WAF = keragaman ASN
11. JANGAN sisipkan cabang tepat setelah kepala 'if' (tubuh if terpotong). Gabungkan ke kondisi yang ada, atau cari akhir blok dulu
12. jangan tebak nama variabel: baca dari baris anchor (di sini 'api_path', bukan 'path')

## Urutan berikutnya
1. hubungkan gateway ke transport worker + catat IP egress per worker
2. bukti rotasi egress nyata (butuh GALARDO_GATEWAY_URL - kredensial anyip.io)
3. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
4. ingest intel REA + pre-flight validasi
5. halaman Override (Goal 3)
6. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
7. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
