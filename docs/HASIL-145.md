# HASIL-145 — boot cetak ke stderr + pool engine diarahkan ke gateway

- tanggal: 2026-10-24 12:20
- KOREKSI: commit d375757 salah label (docs(STATUS)) padahal ikut membawa api.py boot + verify_gateway + HASIL-144
- TEMUAN 1: GAGAL verify_dashboard_pages muncul setelah blok boot ditanam; tersangka: boot menulis ke STDOUT saat api.py di-import. Perbaikan: cetak ke stderr.
- TEMUAN 2: /proxy/status masih menunjuk pool 'residential' padahal gateway didaftarkan sebagai pool 'gateway' -> engine belum tentu memakainya. Perbaikan: boot menyetel GALARDO_PROXY_POOL ke nama pool gateway bila belum diset.
- dashboard_pages rc=0 | gateway rc=0 | test rc=0 | gate rc=0
- bukti: .out/STEP-145-fake.log, .out/STEP-145-dash1..3.txt
