# HASIL-155 - halaman Override (Goal 3) di dashboard

- tanggal: 2026-10-24
- TUJUAN: mengoperasikan pilar 5 (memutus rantai edge->origin) dari UI, bukan hanya curl.
- ISI: halaman "Override" di dashboard/index.html - nav data-p="override" + PAGE_TITLES + RENDER.override.
  Panel memanggil /origins/<domain> (kandidat origin), /egress/status?probe=1 (status egress),
  dan POST /intel/preflight (klaim intel = hipotesis vs pengukuran, divergensi ditampilkan).
- PENGUNCI: tools/verify_dashboard_pages.py (nav <-> PAGE_TITLES <-> RENDER harus konsisten).
- BELUM: verifier HTTP nyata untuk /intel/preflight -> STEP-156 (pola verify_origins.py).
- angka: pages rc=0 | intel rc=0 | wired rc=0 | test rc=0 | gate rc=0
