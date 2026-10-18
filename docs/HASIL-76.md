# HASIL-76 — F-3 (tanpa CSP) & F-4 (CORS * + Bearer)

Status: TUTUP keduanya.

## Temuan
F-4: `Access-Control-Allow-Origin: *` statis; tak ada `Vary`, tak ada cara membatasi
     origin; preflight tak diuji. Untuk API ber-Bearer, `*` tidak salah, tetapi
     tanpa allowlist dan tanpa Vary, respons bisa di-cache lintas origin secara salah.
F-3: dokumen dashboard dikirim tanpa CSP dan tanpa header keamanan lain, sehingga
     tak ada pagar terhadap injeksi skrip / framing.

Catatan penting: SEBELUM step ini tidak ada satu pun verifier yang memeriksa header,
jadi kedua temuan bisa "hijau" tanpa pernah diuji.

## Perbaikan
- `_cors_mode()` + `_cors_allow()`: `GALARDO_CORS_ORIGINS` (dipisah koma) atau `*` (default,
  tanpa regresi). Origin terdaftar di-echo + `Vary: Origin`; origin TAK terdaftar diomit
  (strict) supaya browser benar-benar memblokir - bukan mengirim origin yang salah.
- Header keamanan pada semua respons: `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`.
- CSP pada dokumen HTML (dapat diatur via `GALARDO_CSP`):
  `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline';
   script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none';
   base-uri 'self'; form-action 'self'`
  (CDN dibuang karena dashboard tidak memuat skrip eksternal).
- Preflight `OPTIONS` tetap 204 dan `Access-Control-Allow-Headers` memuat Authorization.

## Cacat yang ketangkap saat pengerjaan (jujur)
Versi pertama `_cors_allow` memakai `daftar[0]` sebagai fallback untuk origin tak
terdaftar -> respons mengirim `ACAO: https://a.test` padahal Origin `https://jahat.test`,
sehingga browser memblokir walau header "ada". Diperbaiki menjadi omit (strict) dan
dikunci oleh cek `C origin tak terdaftar diomit`.

## Bukti
    verify_headers.py -> 21 passed, 0 failed
      termasuk: B ACAO default * / tanpa Vary saat mode * / nosniff / X-Frame DENY /
                CSP di / / frame-ancestors / preflight 204 / Authorization diizinkan
                C origin terdaftar di-echo + Vary / origin tak terdaftar diomit + Vary
    make test -> 79 passed, 0 failed
    verify_devup -> 2/2 ; verify_udp_budget -> 16/16 ; verify_netssl_wired -> 20/20
