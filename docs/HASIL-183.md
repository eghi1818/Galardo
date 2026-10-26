# HASIL-183 - petakan nama tier override (T1/T2/T3) -> forced terbukti

- tanggal: 2026-10-25
- AKAR STEP-182: tier dikirim sebagai "local" padahal nama sebenarnya T1/T2/T3
  (stats.tier_order = ['T2','T1','T3'] -> local-first). apply -> failed_tiers ['local'] -> tanpa shim
  aktif -> probe 'no active shim override' -> forced False.
- FIX: ALIAS_TIER (local->T2, hosts->T1, edge/cf->T3) + _tier() + default None = biarkan urutan default.
  status() kini melaporkan tier_order. Verifier menguji alias + memakai tier T2 eksplisit.
- angka: override rc=0 | pages rc=0 | bukti_wired rc=0 | kit rc=0 | test rc=0 | gate rc=0
