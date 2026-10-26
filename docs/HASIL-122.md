# HASIL-122 — GOAL dieksekusi end-to-end lewat API (bukan cuma hidup)

- tanggal: 2026-10-23 12:27
- rantai: engagement 201 -> approve 200 -> scenario 201 -> test-plan 201 -> approve 200
         -> job 202 -> start 200 (preflight PASS) -> safety ABORT -> evidence -> verify -> audit
- job: job-890956504063 | abort_code ERROR_RATE | error_pct 36.84 > 30.0 (window 5s)
- metrik: requests 20, ok 13, err_5xx 7, p50 1.1 ms
- evidence: evd-job-890956504063, build 201, verify 200 verified=true (13 files, sha256 135799af...)
- audit: 38 entri | overview/alerts: 0/0
- catatan: crash parsing pertama karena /test-jobs/{id}/live mengembalikan {"job": {...}}; sudah dibetulkan

## Bukti mentah
- .out/STEP-122-*.txt

## Arti
- Galardo mengambil keputusan (safety abort) yang bisa diaudit, bukan hanya meneruskan trafik
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
