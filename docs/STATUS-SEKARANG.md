# STATUS SEKARANG — Galardo (otomatis STEP-143)

- waktu  : 2026-10-24 11:53
- HEAD   : a6bb885 test(integration): req() tahan timeout DNS (3 percobaan) - gate hijau; verifikasi wiring gateway
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, seksi 9 MODE B)

## Pondasi (SELESAI & terkunci)
- doktrin GOAL (verify_goal_doctrine); mesin pengguna (verify_auth_users 20 cek); gateway Mode B (verify_gateway 27 cek)
- endpoint /api/v1/gateway/status HIDUP (200) dan /api/v1/proxy/status tidak rusak
- angka terakhir: test rc=0/0 | gate rc=0 | gateway rc=0 | egress rc=0 (SKIP tanpa kredensial)

## Cara jalankan / hentikan app
- jalankan: nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- matikan : pkill -f run_local.py
- port    : API 8090 (lab target 8095/8096 - deteksi lewat /api/v1/health)
- token   : GALARDO_DEV_TOKEN (.env, Bearer)

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
11. jangan sisipkan cabang tepat setelah kepala 'if'; gabungkan ke kondisi yang ada
12. jangan tebak nama variabel; baca dari baris anchor (di sini 'api_path')
13. langkah STATUS yang selalu 'git add -A' ikut meng-commit perubahan lain -> periksa pesan commit
14. tes yang menyentuh jaringan (TXT DNS koler.space) WAJIB punya retry

## Urutan berikutnya
1. hubungkan gateway ke transport worker + catat IP egress per worker
2. bukti rotasi egress nyata (butuh GALARDO_GATEWAY_URL - kredensial anyip.io)
3. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
4. ingest intel REA + pre-flight validasi
5. halaman Override (Goal 3)
6. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
7. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
