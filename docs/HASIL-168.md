# HASIL-168 - cara ukur dibetulkan (window penuh) -> verify_multilane hijau

- tanggal: 2026-10-24
- FIX: verifier mengukur dengan window penuh (ring dibuat per-run) + cek pelayanan lewat log
  _do_request (tidak bergantung jam). Verifier ditulis ulang bersih (tanpa baris akrobatik STEP-167).
- HASIL: semua cek hijau, termasuk 4419 request terhitung, tanpa exception VU.
- angka: ml rc=0 | knee rc=0 | live rc=0 | ch rc=0 | pages rc=0 | test rc=0 | gate rc=0
