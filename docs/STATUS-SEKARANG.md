# STATUS SEKARANG — Galardo (otomatis STEP-132)

- waktu  : 2026-10-24 08:52
- HEAD   : 166b1c1 fix(goal): doktrin menamai diri + verifier doktrin benar + verify_auth_users versi resolver; koreksi klaim HASIL-127
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, termasuk seksi 9 MODE B)

## Angka verifikasi terakhir (jujur)
- verify_auth_users rc=1 | make test rc=0 | make gate rc=2

## SUDAH ada
- doktrin GOAL + penguncinya; verifier lapisan proxy (pool/provider/rotate); rate-limit login 429+Retry-After; cookie Secure saat HTTPS; sesi terpisah; gerbang peran; panel Pengguna; halaman login; tools/verify_egress_rotation.py (SKIP bila GALARDO_GATEWAY_URL kosong)

## BLOCKER (fakta, jangan ditebak)
- POST /api/v1/users dengan Bearer (identitas master usr-operator) memutus koneksi di server (client dapat status 0/RemoteDisconnected), padahal GET /api/v1/users dengan token sama balas 200.
- Akibat: verifier tak bisa membuat user vfy-admin -> cek auth bergantung itu ikut merah.
- Sudah dipasang: pembungkus exception di do_*/_dispatch/_body (traceback ke log, 500+JSON ke client), seed uid master ke users_store, verifier mencetak ekor log saat 0/5xx.
- Lihat bukti: tail -30 .out/galardo-live.log  (cari 'Traceback')

## Cara menjalankan
- app  : nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- port : API 8090 (lab target 8095 — deteksi lewat /api/v1/health)
- token: GALARDO_DEV_TOKEN di .env (Bearer) = identitas master
- admin: data/users.json -> usr-eghi (SUPERADMIN), usr-lihat (APPROVER)
- user verifier: vfy-admin / verifikasi-123

## Urutan berikutnya
1. tutup blocker POST /users (identitas master)
2. backend/gateway.py + wiring Mode B (sticky per worker, catat IP egress per worker)
3. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
4. ingest intel REA + pre-flight validasi
5. halaman Override (Goal 3)
6. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
7. Cloudflare Tunnel; refresh SESSION_STATE/HANDOFF

## Butuh keputusan pemilik
- kredensial anyip.io (mode B: satu gateway) -> GALARDO_GATEWAY_URL, supaya rotasi egress terbukti
- host uji tembak pertama
