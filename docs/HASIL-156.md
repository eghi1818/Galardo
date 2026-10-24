# HASIL-156 - perbaikan RENDER.override + verifier HTTP nyata /intel/preflight

- tanggal: 2026-10-24
- KOREKSI: STEP-155 menyisipkan entri ke DALAM objek literal `const RENDER = {};`, padahal pengunci
  repo memakai pola `^RENDER.<nama> =` -> 2 cek verify_dashboard_pages merah. Entri dipindah ke
  `RENDER.override = async function(){...};` setelah objek kosong; nav `class="active"` ganda dibuang.
- BARU: tools/verify_intel_live.py - boot app sendiri di port bebas, tunggu /health, uji POST
  /api/v1/intel/preflight (kosong, teks, objek) -> 200 + divergensi lengkap, GET != 200, log tanpa
  Traceback. Jalur SKIP kalau app tak bisa di-boot (supaya make gate tetap aman).
- CATATAN: make gate menjalankan SEMUA tools/verify_*.py -> verifier baru otomatis ikut gate.
- angka: pages rc=0 | intel rc=0 | wired rc=0 | live rc=0 | test rc=0 | gate rc=0
