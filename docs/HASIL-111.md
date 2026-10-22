# HASIL-111 — item 10 (DNS manipulation) TUTUP: verifier offline

STEP: 111 — Item: 10.

## Gap yang ditutup
`tools/verify_ownership_rung1.py` SUDAH ada dan TIDAK hampa (9 cek, jalan di gate), tetapi
hanya mencakup rantai adapt/Ladder. Yang belum tersentuh offline:
1. `OwnershipVerifier.verify()` - logika quorum 2-dari-3 resolver. Satu-satunya penguji
   sebelumnya adalah `make own1-live` yang butuh token Cloudflare + DNS nyata, jadi tidak
   pernah jalan di gate maupun CI.
2. Endpoint `POST /targets/*/verify/dns` (422 tanpa challenge, dns_txt_quorum saat ok,
   penyimpanan ownership_proof).
3. Ranting `dns` di `layer_attrib.classify`.

## Yang diubah
- tools/verify_dns_ownership.py (baru, 30 cek): offline penuh dengan
  `ownership.netdns.txt_quorum` di-monkeypatch. Cakupan: primitif, round-trip Challenge,
  quorum ok / label cadangan / semua gagal / kedaluwarsa, attempts & required diteruskan,
  revoke, ranting dns, dan wiring endpoint.
- docs/INVENTARIS.md: item 10 -> SELESAI.

## Catatan
Ada dua artefak kembar untuk rantai yang sama: tests/test_ownership_rung1.py (122 baris,
dipakai `make own1`) dan tools/verify_ownership_rung1.py (262 baris, dipakai gate +
`own1-live`). Berbeda isi - kandidat konsolidasi di langkah lain.

## Bukti
- tools/verify_dns_ownership.py: .out/HASIL-111-verifier.txt
- make gate + make test: .out/HASIL-111-gate.txt, .out/HASIL-111-test.txt
