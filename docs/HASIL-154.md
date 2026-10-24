# HASIL-154 - wiring POST /api/v1/intel/preflight + verifier AST

- tanggal: 2026-10-24
- TUJUAN: menyambungkan mesin intel (STEP-153) ke API supaya klaim intel pihak ketiga bisa
  dikirim dan langsung dibenturkan dengan pengukuran.
- ISI: route POST /api/v1/intel/preflight di backend/api.py (sebelum cabang proxy/status),
  body lewat self._body(), 200 = hasil preflight, 422 = payload tak terbaca.
- VERIFIER: tools/verify_intel_wired.py - AST (import intel, cabang If route, method POST,
  intel.preflight, jalur 200/422, cabang lama utuh) + behavioral preflight.
- CATATAN: tools/step_guard.sh ternyata tipis (cd + git log); jaminan asli = verifier + make test.
- BELUM: halaman Override (Goal 3) di dashboard -> STEP-155.
- angka: intel rc=0 | wired rc=0 | test rc=0 | gate rc=0
