# HASIL-182 - adaptor override pakai API sebenarnya (spec-based)

- tanggal: 2026-10-25
- STATUS: BELUM hijau saat itu (commit ditahan). Diperbaiki di STEP-183.
- TUJUAN: ganti adaptor dari "cari fungsi level modul" ke API sebenarnya routeoverride.
- ISI: backend/override_api.py ditulis ulang spec-based -> OverrideSpec(origin, mode, tiers)
  + apply(spec) -> spec_id -> probe(spec_id) -> forced ; pembersih pakai revert(spec_id) ;
  status pakai list_active()+stats().
- BUKTI (raw): spec_id terbit (`ov-1792974595670`), OverrideSpec terbentuk
  (origin/ paths ['/*'] / mode '404'), revert ketemu.
- AKAR MASIH MERAH: tier dikirim sebagai "local", padahal nama sebenarnya T1/T2/T3
  (stats.tier_order = ['T2','T1','T3']). Akibat: apply -> ok False, failed_tiers ['local'],
  tidak ada shim aktif -> probe 'no active shim override' -> forced False.
- angka (saat itu): override rc=1 (3 cek GAGAL) | pages rc=0 | bukti_wired rc=0 | test rc=0 | gate rc=0
