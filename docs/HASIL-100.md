# HASIL-100 — P2: pool proxy pindah namespace env

STEP: 100 — Item lanjutan P2 (celah tabrakan env).

## Bug yang ditutup
`proxypool.env_key()` membangun `GALARDO_PROXY_<NAMA>` dari prefix yang sama dengan env
provider (`proxy_provider.py`: URL/KEY/AUTH/POOL/TTL/TIMEOUT), sementara `parse_spec()`
mewajibkan `host:port`. Terbukti hidup sebelum perbaikan:

    resolve(key) -> PoolError: port tidak ada pada 'sk-rahasia-123'
    resolve(ttl) -> PoolError: port tidak ada pada '300'
    resolve(url) -> PoolError: port tidak ada pada 'https://contoh.test/api/proxies'

## Yang diubah
- `backend/proxypool.py`: `POOL_PREFIX = "GALARDO_POOL_"` jadi namespace kanonik pool;
  `legacy_env_key()` membaca `GALARDO_PROXY_<NAMA>` sebagai warisan, kecuali untuk nama
  yang ada di `RESERVED` (URL/KEY/AUTH/POOL/TTL/TIMEOUT) yang milik provider;
  `_spec_dari_env()` dipakai `resolve()` dan `credentials()`.
- `tools/verify_proxypool.py`: blok cek baru — namespace baru terbaca, warisan
  non-reserved tetap terbaca, tiga nama reserved tidak melempar, dan `GALARDO_POOL_KEY`
  menang atas `GALARDO_PROXY_KEY`.

## Kompatibilitas
`GALARDO_PROXY_RESIDENTIAL` dan nama non-reserved lain tetap bekerja apa adanya.
`verify_proxypool.py` dan `verify_proxy_provider.py` memakai `pp.env_key()` sehingga
ikut menyesuaikan tanpa disunting.

## Bukti
- `tools/verify_proxypool.py` + `tools/verify_proxy_provider.py`: hijau (.out/HASIL-100-*)
- demo tabrakan: tiga nama reserved tidak lagi melempar
- `make gate` + `make test`: lihat .out/HASIL-100-gate.txt dan .out/HASIL-100-test.txt

## Sisa (STEP-101)
- `docs/KONEKSI-PIHAK-KETIGA.md` (baris ~75, ~154, ~198) dan `docs/DEPLOY-VPS.md:171`
  masih menyebut `GALARDO_PROXY_<NAMA>` untuk pool; perlu ditambah `GALARDO_POOL_`.
- Rekonsiliasi: ROADMAP:155, backfill STEPLOG 81-96 dari commit 58d8261..3f64fd9,
  `EMERGENCY.md` (acuan make test 61 -> 79), `gate.yml` belum memasang node.
- P1 belum disebut tutup: run hijau di tab Actions belum dikonfirmasi (`gh` absen).
