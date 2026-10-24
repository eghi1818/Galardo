# HASIL-161 - live deterministik (direktif ukur) + kanonik kapasitas

- tanggal: 2026-10-24
- AKAR MASALAH live rc=1 (STEP-159): cek POST berbadan memanggil origins.candidates -> crt.sh
  (internet) > timeout 8s -> status=0. BUKAN tabrakan port, BUKAN app rusak (log bersih, GET lolos).
- FIX: direktif payload `ukur: 0` di backend/intel.py (default tetap 1) -> cek utama deterministik;
  jalur ukur nyata tetap diuji terpisah dengan timeout 30s. 5 cek baru di verify_intel.
- KONSOLIDASI KAPASITAS: kanonik = tools/galardo_capacity.py (berbasis backend/engine.py, sudah ada
  sejak STEP-32..39, `make capacity`). Yang baru = pengukur independen stdlib -> target `make capacity-fast`
  (cross-check angka knee, tanpa engine). backend/srccap.py + verify_knee/verify_srccap tetap utuh.
- angka: intel rc=0 | wired rc=0 | live rc=0 skip=0 | cap rc=0 | pages rc=0 | test rc=0 | gate rc=0
