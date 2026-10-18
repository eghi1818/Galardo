# HASIL-78 — Panel dashboard "Tools" (subfinder / nikto / traceroute)

Status: SELESAI.

## Yang dibangun
Halaman `tools` di dashboard single-file: kartu status tiap tool (ADA / TIDAK ADA,
GOAL, path), form jalankan (tool, target, args, timeout), dan panel hasil yang
menampilkan `ok/available/rc/elapsed/reason/parsed` + output mentah.
Nav + `PAGE_TITLES` + `RENDER.tools` ditambahkan BERSAMAAN karena
verify_dashboard_pages.py menuntut ketiganya konsisten.

## Bukti
    verify_dashboard_pages.py -> RESULTS: 7 passed, 0 failed
      nav=15 titles=15 halaman=15 (tools terdaftar di nav, PAGE_TITLES, RENDER)
      ok tiap halaman punya PAGE_TITLES / punya entri nav / punya halaman
      ok node --check sintaks JS
    node --check langsung -> rc 0
    dashboard terkirim: data-p="tools" 1x, RENDER.tools 2x, "tools: 'Tools'" 1x
    GET /api/v1/exttools -> 200 ; CSP tetap ada di /
    make test -> 79 passed, 0 failed ; verify_exttool 16/0 ; verify_headers 22/0

## Catatan
Tool yang belum terpasang (subfinder, nikto) tampil sebagai kartu "TIDAK ADA"
dengan tombol opsi disabled - konsisten dengan sifat fail-open adapter.
Perbaikan kosmetik: `badge()` tidak punya kunci READY -> dipakai HEALTHY/FAILED.
