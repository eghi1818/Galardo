# STATUS SEKARANG — Galardo (otomatis STEP-133)

- waktu  : 2026-10-24 09:27
- HEAD   : 2d1dc5d fix(verify): akar masalah auth = bug probe() (body terkirim sebagai cookie) + status ketat + port milik sendiri; fix(api): seed uid master
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, termasuk seksi 9 MODE B)

## Angka verifikasi terakhir (jujur)
- verify_auth_users rc=1 | make test rc=0 | make gate rc=2
- verifier lain di gate: verify_goal_doctrine OK, verify_egress_rotation OK (SKIP bila gateway kosong)

## Yang SUDAH ada
- doktrin GOAL + penguncinya; verifier lapisan proxy (pool/provider/rotate); rate-limit login 429+Retry-After; cookie Secure saat HTTPS; sesi terpisah dari token; gerbang peran; panel Pengguna; halaman login; pembungkus exception do_*/_dispatch/_body; seed uid master

## Pelajaran penting (jangan diulang)
- 'status 0' dari probe = exception, BUKAN sukses. Selalu pakai 200 <= s < 400.
- Verifier harus memakai port app MILIKNYA (baca dari log sendiri). Kalau scan 8090..8099 dia bisa menabrak app lain dan env-nya beda.
- HASIL-132 salah menyebut POST /users memutus koneksi; koreksinya ada di HASIL-133.

## Cara menjalankan
- app  : nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- port : API 8090 (lab target 8095/8096 — deteksi lewat /api/v1/health)
- token: GALARDO_DEV_TOKEN di .env (Bearer) = identitas master
- admin: data/users.json -> usr-eghi (SUPERADMIN), usr-lihat (APPROVER)
- user verifier: vfy-admin / verifikasi-123

## Urutan berikutnya
1. (selesai) tutup verifier auth
2. backend/gateway.py + wiring Mode B (sticky per worker, catat IP egress per worker)
3. bukti rotasi egress nyata (butuh GALARDO_GATEWAY_URL)
4. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
5. ingest intel REA + pre-flight validasi
6. halaman Override (Goal 3)
7. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
8. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF

## Butuh keputusan pemilik
- kredensial anyip.io (mode B: satu gateway) -> GALARDO_GATEWAY_URL
- host uji tembak pertama
