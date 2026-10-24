# STATUS SEKARANG — Galardo (otomatis STEP-147)

- waktu  : 2026-10-24 12:36
- HEAD   : 1b5fb86 docs(STATUS): origins terkunci
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, seksi 9 MODE B)

## Pondasi terkunci
- doktrin GOAL; mesin pengguna (20 cek); gateway Mode B (28 cek) + boot + pool engine; origins (27 cek) + endpoint
- angka: origins rc=0 | netssl rc=1 | test rc=0 | gate rc=2 | endpoint origins=200
- bila gate masih merah: periksa .out/STEP-147-netssl.txt (verify_netssl_wired)

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
18. JANGAN pakai format % pada URL yang memuat persen -> '%%25' bikin ValueError; pakai konkatenasi

## Urutan berikutnya
1. hubungkan gateway ke transport worker + catat IP egress per worker
2. ingest intel REA + pre-flight validasi
3. halaman Override (Goal 3) + tampilkan kandidat origin
4. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
5. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
6. bukti rotasi egress nyata (setelah kredensial anyip.io)
