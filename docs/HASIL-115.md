# HASIL-115 — V4 run nyata Mode Aktif (penutup PRD)

- tanggal: 2026-10-22 13:44
- harness: make demo -> tools/galardo_demo.py (Goal 2 + Goal 3, proses nyata + HTTP nyata)
- bukti mentah: .out/STEP-115-demo.txt
- hasil: DEMO_OK, down_verified=true, transisi=4, ttr=44.373 s, peak_waiting=288, served=5047, shed_503=0
- gate3: [goal3-blank] applied=['T2'] status=200 body_len=0 forced=True | [goal3-revert] reverted=['T2'] / ok

## Yang dibuktikan
- baseline idle, plafon worker, spike 300 VU ke /api/heavy
- transisi UP -> SUSPECT -> DOWN -> RECOVERING -> RECOVERED dengan time_to_recover
- bukti jenuh: peak_waiting + avg_wait_ms + saturated
- Goal 3: paksa 404, paksa blank, revert

## Dokumen yang ditutup
- INVENTARIS V4 -> SELESAI; seksi Z jadi 'TIDAK ADA PENDING'
- PENDING.md sisa PRD jadi 'tidak ada'; item 10/13/14 dikoreksi SELESAI
