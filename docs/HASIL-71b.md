# HASIL-71b — Kambuhnya flake F-1 (dispatch 409) + perbaikan anggaran retry

Status: TUTUP.

## Bukti kejadian
Gate STEP-71 gagal 1 kali:
    RESULTS: 78 passed, 1 failed
    FAIL: degraded-target job dispatched (async preflight DB checks PASS) — st=409
Setelah perbaikan, 3 ulangan berturut: 79/79, 79/79, 79/79.

## Sebab (bukan tebakan)
- /start fail-fast 409 selama preflight async belum PASS (backend/api.py:996).
- Tes ini mendegradasi target lebih dulu (tests/tests_integration.py:287), sehingga
  preflight memuat probe baseline yang menunggu timeout — bersinggungan dengan
  F-7 (probe UDP lambat, MASIH TERBUKA).
- Anggaran retry helper tes lama: tries=30 x delay=0.4 = 12 s -> kadang kalah.

## Perbaikan
tests/tests_integration.py: start_job(tries=60, delay=0.5) -> anggaran 30 s,
di atas worst-case preflight. Semantik API tidak diubah (409 tetap jawaban benar
saat preflight belum PASS).

## Catatan
F-1 tetap TUTUP untuk diagnosisnya; F-1b mencatat anggaran retry-nya kurang.
Akar sisa ada di F-7 (probe lambat) yang masih terbuka.
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
