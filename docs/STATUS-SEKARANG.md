# STATUS SEKARANG — Galardo (otomatis STEP-135)

- waktu  : 2026-10-24 09:42
- HEAD   : aa87d48 fix(verify): areq terima non-403 (422 tidak dibuang) + isolasi app verifier + diagnosa cookie
- branch : main | origin/main...HEAD: 0	0
- doktrin: docs/GOAL-GALARDO.md (MENGIKAT, termasuk seksi 9 MODE B)

## Angka verifikasi terakhir
- verify_auth_users rc=0 | make test rc=0 | make gate rc=2
- kalau ketiganya 0: mesin pengguna SELESAI dan terkunci -> lanjut ke backend/gateway.py (Mode B)

## Yang SUDAH ada dan hijau
- doktrin GOAL + penguncinya; verifier lapisan proxy (pool/provider/rotate); rate-limit login 429+Retry-After; cookie Secure saat HTTPS; sesi terpisah dari token; gerbang peran; panel Pengguna; halaman login; pembungkus exception do_*/_dispatch/_body; seed uid master; verify_auth_users v7

## PELAJARAN WAJIB (jangan diulang) — semua ini sudah pernah menelan waktu
1. status 0 dari probe = exception, BUKAN sukses. Selalu '200 <= s < 400'.
2. probe(method, path, body, cookie, ...) — body SEBELUM cookie. Salah urutan = TypeError = 0.
3. Jalur cadangan jangan menyaring status: 'non-403' bukan '200..399' (422 harus lolos).
4. Verifier WAJIB memakai app miliknya sendiri (port dibaca dari log sendiri) dan mematikan app lain dulu.
5. Dua proses app berbagi data/users.json + data/sessions.json -> sesi bisa saling menimpa.
6. Anchor patch bisa MISS tanpa error; selalu verifikasi dengan grep sesudah patch.
7. Jangan sebut sesuatu selesai tanpa keluaran nyata; kalau merah, tulis merah.

## Cara menjalankan
- app  : nohup sh -c 'cd backend && exec python3 -u run_local.py' > .out/galardo-live.log 2>&1 &
- port : API 8090 (lab target 8095/8096 — deteksi lewat /api/v1/health)
- token: GALARDO_DEV_TOKEN (.env, Bearer) = identitas master; admin: usr-eghi/SUPERADMIN
- user verifier: vfy-admin / verifikasi-123

## Urutan berikutnya (doktrin)
1. backend/gateway.py + wiring Mode B (sticky per worker, catat IP egress per worker)
2. bukti rotasi egress nyata (butuh GALARDO_GATEWAY_URL — kredensial anyip.io menyusul)
3. Origin IP discovery (crt.sh / DNS historis / kebocoran header)
4. ingest intel REA + pre-flight validasi
5. halaman Override (Goal 3)
6. lane/multi-lane, botnet/IoT, check-host per-negara, make capacity
7. Cloudflare Tunnel (pihak ketiga) + refresh SESSION_STATE/HANDOFF

## Butuh keputusan pemilik
- kredensial anyip.io (mode B: satu gateway) -> GALARDO_GATEWAY_URL (pemilik: 'nanti saja')
- host uji tembak pertama
