# HASIL-112 — item 14 TUTUP: verifier worm + celah "yatim" ditutup

STEP: 112 — Item: 14.

## Celah nyata yang ditemukan
`WormTree.alive()` hanya melacak AKAR (self.procs); keturunan lahir dari proses agen
sehingga koordinator tidak memegang handle-nya. Akibatnya `wait_all_dead()` hanya berarti
"akar sudah mati". Klaim "0 yatim" di harness ditopang `reap()` yang MEMBUNUH sisa proses,
bukan membuktikan sisa itu nol - kalau reap() dihapus, harness tetap melaporkan all_dead
meski keturunan masih hidup.

## Yang diubah
- backend/worm.py: `alive_all()` (hitung proses run ini lewat `pgrep -f run_id`);
  `wait_all_dead()` kini memakainya sehingga benar-benar berarti semua mati.
- tools/verify_worm.py (baru, 19 cek): A aritmetika pohon; B cascade end-to-end
  (lahir 14 proses -> stop renew -> semua mati -> nol yatim SEBELUM reap);
  C agen dengan lease hilang bunuh diri sendiri; D selama renew agen tetap hidup;
  E pengunci sumber (reap pakai pgrep, agen fail-closed, env terdokumentasi di 3 dokumen).
- docs/INVENTARIS.md: item 14 -> SELESAI.

## Bukti
- tools/verify_worm.py: .out/HASIL-112-verifier.txt (memuat waktu cascade & sisa proses)
- make gate + make test: .out/HASIL-112-gate.txt, .out/HASIL-112-test.txt
