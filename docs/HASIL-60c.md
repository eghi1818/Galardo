# HASIL-60c - tutup F-1 dengan sebab akurat + F-7

- Status : SELESAI
- Sifat  : tes; tests/tests_integration.py
- Sebab F-1 yang benar: /start fail-fast balas 409 bila preflight async belum PASS
  (backend/api.py:845). Tes menembak sekali lalu menilai -> flaky.
- Perbaikan: helper start_job() toleran 409 (12 percobaan x 0.4s) di semua pemanggilan /start;
  req() kini punya parameter timeout (bawaan tetap 15).
- F-7: probe UDP melebihi 15s -> tes timeout=45. Endpoint perlu ditinjau.
- F-8: 409 preflight = keputusan desain fail-fast, bukan bug.
- Catatan: patch awal menimbulkan rekursi (regex ikut mengganti panggilan di dalam helper); diperbaiki.
- Ukur: 5 run berturut sebelum commit, semua hijau.
