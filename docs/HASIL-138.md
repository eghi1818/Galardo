# HASIL-138 — preflight OPTIONS 204 (mode CORS ketat) = hasil eksperimen

- tanggal: 2026-10-24 10:11
- verify_headers GAGAL deterministik di cek A 'preflight OPTIONS balas 204' (22 passed, 1 failed); bukan flaky, bukan docker, bukan pkill
- eksperimen: pembungkus do_* dilepas -> verify_headers rc=1 (dengan pembungkus rc=1)
- auth rc=0 | test rc=0 | gate rc=2
- bukti: .out/STEP-138-h1.txt (dengan pembungkus), .out/STEP-138-h2.txt (tanpa pembungkus)
