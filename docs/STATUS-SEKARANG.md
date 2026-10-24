# STATUS SEKARANG — Galardo (otomatis STEP-144)

- waktu  : 2026-10-24 12:12
- HEAD   : d128c9a docs(STATUS): wiring terverifikasi + 2 pelajaran baru
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, seksi 9 MODE B)

## Pondasi (SELESAI dan terkunci)
- doktrin GOAL; mesin pengguna (20 cek); gateway Mode B (28 cek) + boot pendaftaran ke proxypool
- endpoint /api/v1/gateway/status hidup; proxy/status tidak rusak
- angka: gateway rc=0 | egress rc=0 (SKIP tanpa kredensial) | test rc=0 | gate rc=2

## Cara jalankan / hentikan app
- jalankan: nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- nohup = app tetap hidup walau jendela terminal ditutup (disengaja: Galardo Aktif)
- matikan : pkill -f run_local.py   (atau kill %1)
- port    : API 8090 (lab target 8095/8096 - deteksi lewat /api/v1/health)
- token   : GALARDO_DEV_TOKEN (.env, Bearer)

## YANG DITUNGGU DARI PEMILIK
- kredensial anyip.io (mode B) -> isi GALARDO_GATEWAY_URL di .env
  bentuk: host:port | user:pass@host:port | scheme://host:port
  setelah diisi: python3 tools/verify_egress_rotation.py harus mencetak IP unik 2 atau lebih
- host uji tembak pertama

## Pelajaran wajib (jangan diulang)
1. status 0 dari probe = exception, BUKAN sukses -> pakai 200 <= s < 400
2. probe(method, path, body, cookie, ...) - body SEBELUM cookie
3. jalur cadangan jangan menyaring status: non-403, bukan 200..399
4. verifier pakai port app sendiri; jangan pkill app verifier lain
5. sesi hidup di MEMORI -> dua proses app = sesi saling menimpa
6. anchor patch bisa MISS tanpa error; verifikasi dengan grep
7. cek verifier atas TEKS SUMBER rapuh terhadap rename -> pakai regex
8. guard penyisipan harus diuji (jangan pakai split yang sudah memuat penanda)
9. hipotesis bukan fakta (gate merah karena docker / karena pkill dua-duanya SALAH)
10. Mode B: rotasi per KONEKSI/WORKER, bukan per request; penentu WAF = keragaman ASN
11. jangan sisipkan cabang tepat setelah kepala if; gabungkan ke kondisi yang ada
12. jangan tebak nama variabel; baca dari baris anchor (di sini api_path)
13. langkah STATUS yang git add -A ikut meng-commit perubahan lain -> periksa pesan commit
14. tes yang menyentuh jaringan (TXT DNS) WAJIB punya retry
15. nohup = app hidup walau terminal ditutup; matikan dgn pkill -f run_local.py
16. zsh mengekspansi tanda seru walau di dalam kutip ganda -> jalankan setopt no_bang_hist

## Urutan berikutnya
1. bukti rotasi egress nyata (butuh GALARDO_GATEWAY_URL)
2. hubungkan gateway ke transport worker + catat IP egress per worker
3. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
4. ingest intel REA + pre-flight validasi
5. halaman Override (Goal 3)
6. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
7. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF
