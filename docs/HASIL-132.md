# HASIL-132 — bongkar RemoteDisconnected + dokumen status

- tanggal: 2026-10-24 08:52
- TEMUAN: POST /api/v1/users dengan Bearer (uid master) memutus koneksi; GET /users token sama 200
- perbaikan: pembungkus exception do_*/_dispatch/_body (traceback ke log, 500 JSON ke client)
- perbaikan: seed uid master ke users_store
- verifier: cetak ekor log app saat 0/5xx
- docs/STATUS-SEKARANG.md + rujukan di rantai onboarding

## Angka jujur
- auth rc=1 | test rc=0 | gate rc=2
