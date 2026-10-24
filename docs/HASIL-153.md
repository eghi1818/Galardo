# HASIL-153 - ingest intel (hipotesis) + pre-flight validasi

- tanggal: 2026-10-24
- TUJUAN: menutup celah doktrin "REA = hipotesis, Galardo = pengukuran" -> klaim intel pihak ketiga
  WAJIB dibenturkan dengan hasil ukur, divergensinya dicatat, bukan ditelan.
- ISI: backend/intel.py (parse dict/JSON/teks, normalisasi host+IP, divergences cocok/beda/
  tak diklaim/tak terukur, ringkasan, preflight, measured_from lewat origins+egress).
- VERIFIER: tools/verify_intel.py BEHAVIORAL (panggil fungsi, cek efek; tes jaringan punya jalur SKIP).
- BELUM: wiring endpoint /intel/preflight + halaman Override (Goal 3) -> STEP-154.
- angka: intel rc=0 | test rc=0 | gate rc=0
