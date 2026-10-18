# HASIL-85 — P2: adapter provider proxy/residential

Status: SELESAI (fail-open; siap diisi kredensial kapan pun).

## Kondisi awal (temuan)
backend/proxypool.py SUDAH fail-open: resolve() membaca registry + env GALARDO_PROXY_<NAMA>
dan mengembalikan None bila kosong, sehingga jalur probe jatuh ke koneksi langsung.
Yang belum ada: pengambil daftar dari API provider + rotasi.

## Yang dibangun
- backend/proxy_provider.py: fetch API provider (netssl.context), parser toleran
  (list dict host/port|ip/username, bungkusan data/proxies/results/list, list string,
  "user:pass@host:port", "host:port:user:pass", teks baris-per-baris), cache TTL,
  rotasi round-robin, fail-open (daftar lama dipertahankan bila fetch gagal).
- proxypool.resolve(): hook konsultasi provider (import lazy, dibungkus try/except).
- Endpoint: GET /api/v1/proxy/status (VIEWER), POST /api/v1/proxy/refresh|rotate (TEST_OPERATOR).
- tools/verify_proxy_provider.py: 24 cek offline (8 bentuk respons, fail-open, TTL, rotasi).
- Koreksi dokumen: nama env Cloudflare (GALARDO_CF_ACCOUNT_ID / GALARDO_CF_ZONE_ID /
  GALARDO_CF_ZONE_NAME), bukan GALARDO_CF_ZONE.

## Bukti
    verify_proxy_provider.py -> RESULTS: 24 passed, 0 failed
    GET /api/v1/proxy/status -> 200 {"configured": false, ...} (tanpa kredensial)
    POST /api/v1/proxy/refresh -> 200 ; POST /api/v1/proxy/rotate -> 200
    make gate -> rc=0 (semua verifier ok) ; make test 79/0

## Langkah Anda berikutnya (untuk mengaktifkan)
1. Pilih provider (AnyIP / Bright Data / IPRoyal / Smartproxy) dan ambil paket terkecil.
2. Salin base URL API + API key, set:
       GALARDO_PROXY_URL=...
       GALARDO_PROXY_KEY=...
       GALARDO_PROXY_POOL=residential
3. Kirim bentuk respons API-nya ke agen; bila perlu tinggal sempitkan parser.
4. Uji: GET /api/v1/proxy/status -> configured true, count > 0.

## Koreksi (blok 86) — jujur
Commit 752fccf ter-push padahal gate MERAH (rc=2). Sebab: `make gate` bergantung pada
`test:`, jadi saat `make test` gagal, make berhenti sebelum loop verifier -> 0 verifier
dijalankan. Dua bug ikut ketahuan dan ditutup:
1. hook resolve() mengembalikan 4-tuple (registry mentah) padahal resolve() = 2-tuple
   -> kini `return (e[0], e[1])`; verifier menambah cek "resolve selalu 2-tuple".
2. verifier memakai nama env huruf kecil, padahal env_key() menghasilkan huruf besar
   -> kini memakai proxypool.env_key().
