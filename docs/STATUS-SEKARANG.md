# STATUS SEKARANG — Galardo (otomatis STEP-148)

- waktu  : 2026-10-24 12:49
- HEAD   : 4e9e3c2 fix(origins,gateway): pakai SSL context netssl pada semua fetch HTTPS
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, seksi 9 MODE B)

## Pondasi terkunci
- doktrin GOAL; mesin pengguna (20 cek); gateway Mode B (28 cek); origins (29 cek) + endpoint; semua fetch HTTPS lewat netssl
- angka: netssl rc=0 | origins rc=0 | gateway rc=0 | test rc=0 | gate rc=0

## Cara jalankan / hentikan app
- jalankan: nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- matikan : pkill -f run_local.py
- port    : API 8090 (lab target 8095/8096 - deteksi lewat /api/v1/health)

## YANG DITUNGGU DARI PEMILIK
- kredensial anyip.io (mode B) -> GALARDO_GATEWAY_URL di .env
- host uji tembak pertama

## Pelajaran wajib (jangan diulang)
1. status 0 dari probe = exception, BUKAN sukses -> pakai 200 <= s < 400
2. probe(method, path, body, cookie, ...) - body SEBELUM cookie
3. jalur cadangan jangan menyaring status: non-403, bukan 200..399
4. verifier pakai port app sendiri; jangan pkill app verifier lain
5. sesi hidup di MEMORI -> dua proses app = sesi saling menimpa
6. anchor patch bisa MISS tanpa error; verifikasi dengan grep
7. cek verifier atas TEKS SUMBER rapuh terhadap rename -> pakai regex
8. guard penyisipan harus diuji
9. hipotesis bukan fakta (docker/pkill dua-duanya SALAH)
10. Mode B: rotasi per KONEKSI/WORKER; penentu WAF = keragaman ASN
11. jangan sisipkan cabang tepat setelah kepala if; gabungkan atau sisipkan sebelum if lengkap
12. jangan tebak nama variabel; baca dari baris anchor
13. langkah STATUS yang git add -A ikut meng-commit perubahan lain
14. tes yang menyentuh jaringan WAJIB punya jalur SKIP/retry
15. nohup = app hidup walau terminal ditutup; matikan dgn pkill -f run_local.py
16. zsh mengekspansi tanda seru walau di kutip ganda -> setopt no_bang_hist
17. kode saat IMPORT jangan menulis ke stdout -> pakai stderr
18. jangan pakai format % pada URL yang memuat persen -> pakai konkatenasi
19. SEMUA fetch HTTPS di backend wajib pakai context dari netssl (verify_netssl_wired menjaganya)
20. modul baru di backend: tiru pola modul lama (import netssl, jalur SKIP jaringan, tulis ke stderr)

## Urutan berikutnya
1. hubungkan gateway ke transport worker + catat IP egress per worker
2. ingest intel REA + pre-flight validasi
3. halaman Override (Goal 3) + tampilkan kandidat origin
4. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
5. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
6. bukti rotasi egress nyata (setelah kredensial anyip.io)
