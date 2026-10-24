# HASIL-146 — Origin IP discovery (pilar 5)

- tanggal: 2026-10-24 12:28
- backend/origins.py: parse crt.sh (list/dict/bytes/str, dedupe, filter domain), pola host edge vs petunjuk origin, klasifikasi berlapis, resolve DNS tahan error, candidates() berurut dari paling menjanjikan
- tools/verify_origins.py: 27 cek (sebagian live ke crt.sh, SKIP kalau jaringan gagal)
- endpoint /api/v1/origins/<domain>: hasil=500
- origins rc=1 | test rc=0 | gate rc=2
- catatan jujur: klasifikasi edge-maybe memakai prefix CDN yang KASAR; bukti asli = request ke IP dengan Host header target
