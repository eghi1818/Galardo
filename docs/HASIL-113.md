# HASIL-113 — item 9 (botnet IoT global): API simetris + REGISTRY dipulihkan

- tanggal: 2026-10-22 13:06
- HEAD sebelum commit: a364293
- verifier tools/verify_srccap.py: 39 passed / 0 failed
- gate: rc=0 (     370 baris bukti)
- test: RESULTS: 82 passed, 0 failed, 1 skipped

## Akar masalah
- Patch percobaan kedua menyisipkan metode mark_proven dengan mengganti blok fungsi modul,
  dan baris 'REGISTRY = SourceRegistry()' ikut terhapus (di HEAD baris 381).
- REGISTRY.load() NameError ditelan except -> import sukses palsu; mark_proven modul NameError;
  tools/galardo_srccap.py AttributeError.

## Perbaikan
- REGISTRY = SourceRegistry() dipulihkan tepat sebelum ensure_local().
- SourceRegistry.mark_proven() ada sebagai metode, simetris dengan pick()/probe()/matrix().
- Fungsi modul mark_proven() mendelegasikan ke REGISTRY global (dipakai api.py).
- Smoke dua jalur lulus; sumber tidak dikenal -> SourceError.
