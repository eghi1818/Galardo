# HASIL-180 - panel Override edge di dashboard + endpoint status/terapkan/bersihkan

- tanggal: 2026-10-25
- TEMUAN TEGAS: routeoverride.py sudah punya OVERRIDE_HEADER = "X-Galardo-Override" (pembeda 404 kita
  vs 404 asli) - modal utama untuk mode MATI_OVERRIDE di verdict.py.
- ISI: backend/override_api.py (adaptor defensif, tidak pernah melempar) + 3 endpoint
  (GET /override/status, POST /override/terapkan, POST /override/bersihkan) + bagian
  "Edge override (Goal 3)" di halaman Override dashboard (domain, mode 404/410/503/blank, tombol).
- VERIFIER: tools/verify_override_wired.py (AST + behavioral, 18 cek).
- angka: override rc=0 | pages rc=0 | bukti_wired rc=0 | kit rc=0 | test rc=0 | gate rc=0
