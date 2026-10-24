# HASIL-137 — gate merah = verify_headers.py (bukan docker)

- tanggal: 2026-10-24 10:01
- KOREKSI HASIL-136: 'gate rc=2 karena docker' SALAH. docker SIAP; penyebabnya verifier verify_headers.py GAGAL.
- gate: 41 verifier, hanya verify_headers yang merah; verify_auth_users ok di dalam gate
- tindakan: default GALARDO_VERIFY_KILL_OTHERS diubah 1 -> 0 supaya verifier auth tidak membunuh app verifier lain (dugaan kuat penyebab)
- verify_headers rc langsung=1 | auth rc=0 | test rc=0 | gate rc=2
- isi keluaran verify_headers: .out/STEP-137-headers.txt
