# HASIL-88 — P3b (poles image) + P4 (rate limit)

Status: SELESAI keduanya.

## P3b - celah yang ketangkap dari bukti P3
- `traceroute` tidak ada di image (di host ada) -> ditambahkan ke layer apt.
- nikto mencetak "SSL: support not available" -> ditambahkan libnet-ssleay-perl +
  libio-socket-ssl-perl supaya nikto bisa memindai target HTTPS.

## P4 - rate limit (token bucket per klien)
- backend/ratelimit.py: parse spec ("60/m", "120/60s", "300/h", "0"=mati), kunci =
  token Authorization bila ada (else IP), exempt /health + file statis, 429 + Retry-After.
  Aktif hanya bila GALARDO_RATE_LIMIT diisi (default OFF agar tidak mengubah perilaku
  e2e yang membanjiri API).
- api.py: cek di awal _dispatch, _json mengirim Retry-After, GET /api/v1/ratelimit.
- tools/verify_ratelimit.py: 18 cek offline.

## Bukti
    verify_ratelimit.py -> RESULTS: 18 passed, 0 failed
    HTTP limit 5/m: 5 permintaan pertama 200, sisanya 429 + header Retry-After
    /api/v1/health tetap 200 walau limit habis
    make gate rc=0 ; make test 79/0
