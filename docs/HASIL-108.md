# HASIL-108 — koreksi INVENTARIS item 13 + rekam permukaan item 10

STEP: 108.

## Yang ditutup
Langkah INVENTARIS di STEP-107 gagal tanpa menggagalkan blok: regex `^\| Item 13 \|`
menuntut '|' tepat setelah "Item 13 ", sedangkan barisnya `| Item 13 UDP reflection | ...`.
Akibatnya item 13 masih tertulis SEBAGIAN padahal verifier-nya sudah ada dan hijau, dan
berkas INVENTARIS tidak ikut ter-commit di STEP-107. Kini dikoreksi jadi SELESAI.

## Rekam permukaan item 10
Hasil pembacaan ada di .out/HASIL-108-gate.txt pendamping; inti: quorum TXT
(/targets/*/verify/dns), lapisan dns di layer_attrib.py, dan probe_spoof di udp_probe.
Dijalankan langsung (tanpa root dan dengan root) sebagai langkah pertama sebelum menulis
verifier - pelajaran dari dua bug terakhir yang lolos karena jalur ter-wire tidak pernah
dipanggil end-to-end.

## Bukti
- make gate + make test: .out/HASIL-108-gate.txt, .out/HASIL-108-test.txt
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
