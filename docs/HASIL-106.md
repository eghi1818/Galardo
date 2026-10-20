# HASIL-106 — recovery monitor kini benar-benar bisa diverifikasi

STEP: 106 — Item: V7 baru (docs/INVENTARIS.md).

## Bug yang ditemukan dan ditutup
`_begin_recovery()` hanya membuat probe pengganti bila `ctx.probe` FALSY:

    if not (ctx and ctx.probe):        # buat standalone probe

Sementara untuk job terminal (ABORTED), thread probe sudah dimatikan lewat
`ctx.probe.stop.set()` di abort path. Jadi `ctx.probe` masih truthy tetapi `is_alive()`
False -> cabang pengganti dilewati -> cek fail-closed di bawahnya menyetel RECOVERY_FAILED
dan `return` SEBELUM `_recover_thread` pernah dijalankan.

Akibat: recovery tidak pernah bisa diverifikasi untuk job terminal mana pun - padahal
itulah satu-satunya kasus yang recovery tangani. Gejala: `lewat_RECOVERY_WAIT=False`,
status jatuh ke RECOVERY_FAILED dalam waktu jauh di bawah satu detik.

Catatan proses: percobaan patch pertama DILEWATI karena penjaga idempotensi cocok pada
baris fail-closed (550) yang memang sudah punya is_alive(), bukan pada baris sasaran (532).
Penjaga sekarang memakai penanda komentar yang unik.

## Yang diubah
- backend/orchestrator.py: syarat spawn probe pengganti jadi
  `if not (ctx and ctx.probe and ctx.probe.is_alive())` + komentar alasan; cek fail-closed
  di bawah kini benar-benar jaring terakhir. Ditambah toleransi nama state
  ("HEALTHY" atau "RECOVERED") di `_recover_thread` bila probe memakai nama lain.
- tests/tests_integration.py: blok recovery tanpa penjaga COMPLETED-only, sadar-status
  (ABORTED -> ABORTED, COMPLETED -> COMPLETED; RECOVERY_FAILED = gagal nyata).
- docs/INVENTARIS.md: baris V7 ditambahkan.

## Bukti
- make test: .out/HASIL-106-test.txt (harus memuat "recovery: lewat_RECOVERY_WAIT=True
  status_akhir=ABORTED")
- make gate: .out/HASIL-106-gate.txt
