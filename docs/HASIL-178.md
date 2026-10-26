# HASIL-178 - fix generator kit (ONBOARDING) + verifier bukti_wired + jejak override

- tanggal: 2026-10-25
- MERAH STEP-177: (a) kit tidak punya ONBOARDING_PROMPT.txt karena generator mencari nama yang salah;
  (b) verify_bukti_wired setengah terkonversi evidence->bukti (sed tidak cocok).
- FIX: generator mencari bentuk ONBOARDING apa pun + fallback otomatis + salin docs/*.md ke kit;
  verify_bukti_wired ditulis ulang bersih (mod list verdict/falsify/bukti, cek route /bukti).
- JEJAK: lihat .out/step178-gate.txt bagian JEJAK OVERRIDE (target make t3, routeoverride, docs bukti).
- angka: kit rc=0 | bukti_wired rc=0 | bukti rc=0 | falsify rc=0 | verdict rc=0 | test rc=0 | gate rc=0
