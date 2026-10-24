# STATUS SEKARANG — Galardo (otomatis STEP-150)

- waktu  : 2026-10-24 15:32
- HEAD   : 6cd7793 docs(STATUS): egress recorder tercatat
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, seksi 9 MODE B)

## Pondasi terkunci
- doktrin GOAL; mesin pengguna (20 cek); gateway Mode B (28 cek); origins (29 cek); egress recorder (12 cek); rantai pool->transport terbukti (verify_egress_wired)
- endpoint hidup: /gateway/status, /origins/<domain>, /egress/status(+?probe=1)
- JALUR SUDAH OTOMATIS: proxy.py resolve pool dari GALARDO_PROXY_POOL, boot set ke 'gateway', transport.set_proxy
- angka: wired rc=1 | record rc=0 | test rc=0 | gate rc=2

## Cara jalankan / hentikan app
- jalankan: nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- matikan : pkill -f run_local.py
- port    : API 8090 (lab target 8095/8096 - deteksi lewat /api/v1/health)

## YANG DITUNGGU DARI PEMILIK
- kredensial anyip.io (mode B) -> GALARDO_GATEWAY_URL di .env; JANGAN set GALARDO_PROXY_POOL manual (boot yang mengatur)
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
11. jangan sisipkan cabang tepat setelah kepala if; sisipkan sebelum if lengkap
12. jangan tebak nama variabel; baca dari baris anchor
13. langkah STATUS yang git add -A ikut meng-commit perubahan lain
14. tes yang menyentuh jaringan WAJIB punya jalur SKIP/retry
15. nohup = app hidup walau terminal ditutup; matikan dgn pkill -f run_local.py
16. zsh mengekspansi tanda seru walau di kutip ganda -> setopt no_bang_hist
17. kode saat IMPORT jangan menulis ke stdout -> pakai stderr
18. jangan pakai format % pada URL yang memuat persen -> pakai konkatenasi
19. SEMUA fetch HTTPS di backend wajib pakai context dari netssl
20. pool engine dibaca dari GALARDO_PROXY_POOL oleh proxy.py; boot menyetelnya ke 'gateway'

## Urutan berikutnya
1. ingest intel REA + pre-flight validasi
2. halaman Override (Goal 3) + tampilkan kandidat origin + egress
3. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
4. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
5. bukti rotasi egress nyata (setelah kredensial anyip.io)
