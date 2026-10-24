# HASIL-157 - verifier HTTP /intel/preflight non-skip

- tanggal: 2026-10-24
- MASALAH: STEP-156 commit dengan verify_intel_live = [skip]; endpoint masih hanya lolos AST.
- PERBAIKAN: booter multi-strategi (backend/run_local.py dari ROOT, dengan --port, dari cwd backend,
  lalu `make run`), deteksi siap lewat regex 'listening on http://127.0.0.1:PORT' (api.py:1942),
  bunuh process-group, log permanen .out/intel-live-app.log + 30 baris terakhir dicetak saat gagal.
- angka: pages rc=0 | intel rc=0 | wired rc=0 | live rc=0 | skip=0 | test rc=0 | gate rc=0
