# HASIL-185 - siapkan deploy VPS (skrip + prosedur + pengunci)

- tanggal: 2026-10-25
- ISI: tools/deploy_vps.sh (prasyarat, cek .env, cek port, WAJIB make gate + make test di VPS,
  cetak langkah berikut) + `make deploy-vps` + prosedur rsync/scp di docs/DEPLOY-VPS.md.
- VERIFIER: tools/verify_deploy_vps.py (offline, 14 cek) - mencegah "pindah VPS" jadi langkah buta.
- angka: deploy_vps rc=0 | hasil_lengkap rc=0 | kit rc=0 | test rc=0 | gate rc=0
