# HASIL-159 - mesin kapasitas (knee) + make capacity

- tanggal: 2026-10-24
- TUJUAN: KPI kapasitas Galardo = ANGKA KNEE + TTR, bukan throughput saja.
- ISI: backend/capacity.py (beban bertingkat per konkurensi via threading+urllib, hitung rps/p50/p95/
  err_rate, deteksi knee = p95 > 2x baseline ATAU err_rate > 5%, hitung TTR, ringkasan puncak) +
  tools/capacity.py (CLI --url/--steps/--detik/--json) + target `make capacity`.
- VERIFIER: tools/verify_capacity.py behavioral, target HTTP dibuat sendiri (tanpa app/internet):
  14 cek (struktur, ok>0, total=ok+err, p95>=p50, knee/ttr/ringkasan, target lambat, target mati).
- angka: cap rc=0 | intel rc=0 | wired rc=0 | live rc=0 | pages rc=0 | test rc=0 | gate rc=0

## CATATAN KONSOLIDASI (dari STEP-161)
- `tools/galardo_capacity.py` (kanonik, berbasis engine, `make capacity`) TETAP dipakai.
- `backend/capacity.py` + `tools/capacity.py` = pengukur independen stdlib -> target `make capacity-fast`,
  dipakai sebagai pembanding silang angka knee, bukan pengganti.
