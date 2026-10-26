# HASIL-181 - adaptor override diarahkan ke REGISTRY (percobaan pertama)

- tanggal: 2026-10-25
- STATUS: BELUM hijau saat itu (3 cek GAGAL); akar diperbaiki di STEP-182 lalu STEP-183.
- TUJUAN: membuat adaptor menyentuh mesin override yang sebenarnya (bukan fungsi level modul).
- ISI: override_api REGISTRY-first + probe() untuk membuktikan forced; verifier dituntut
  "metode benar-benar ketemu", bukan hanya "tidak melempar".
- BUKTI (raw): uji cepat -> terapkan 'hasil': None 'sumber': 'apply' ; bersihkan 'sumber': None
  'catatan': 'fungsi clear tidak ditemukan'. Verifier: 3 cek GAGAL.
- KOREKSI: draft HASIL-181 menulis override rc=0 padahal rc=1.
- angka (saat itu): override rc=1 (3 GAGAL) | pages rc=0 | bukti_wired rc=0 | test rc=0 | gate rc=0
