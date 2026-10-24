# HASIL-143 — tes DNS tidak tahan jaringan + wiring gateway terverifikasi

- tanggal: 2026-10-24 11:53
- KOREKSI: commit 0f140e7 salah label ('docs(STATUS)') padahal ikut membawa wiring api.py + verify_gateway + HASIL-142 (langkah STATUS selalu git add -A)
- wiring /gateway/status TERVERIFIKASI: endpoint 200, proxy/status tetap 200, verify_gateway 27 cek hijau
- AKAR tes merah: tests_integration POST /targets/tgt-lab/verify/dns -> verifikasi TXT DNS ke internet, intermiten (lolos di STEP-136, gagal di STEP-135 & STEP-142)
- perbaikan: helper req() diberi 3 percobaan + jeda 2s khusus timeout
- hasil: test rc=0 / 0 | gate rc=0 | gateway rc=0 | egress rc=0
