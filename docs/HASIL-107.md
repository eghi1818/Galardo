# HASIL-107 — item 13 (UDP reflection): bug runtime ditutup + verifier pengunci

STEP: 107 — Item: 13.

## Bug yang ditemukan dan ditutup
`rotate_source_ports()` (udp_probe.py:246) memakai variabel `deadline` yang TIDAK pernah
didefinisikan - bukan parameter, bukan variabel modul. Memanggilnya selalu NameError.
Karena `probe_all()` memanggilnya tanpa pelindung, endpoint `POST /sources/*/udp` ikut
gagal: item 13 tidak pernah benar-benar berjalan end-to-end.

Tidak terdeteksi karena tak ada verifier yang memanggil `probe_all` dengan fungsi asli;
`verify_udp_budget.py` hanya menguji pagar budget dan meng-monkeypatch semua tahap.

Dua kebocoran pagar budget sekaligus ditutup: `probe_dns()` menerima `deadline` tetapi
tidak meneruskannya ke `_probe_many()`, dan `probe_all()` tidak meneruskan `deadline`
ke `rotate_source_ports()`.

## Yang diubah
- backend/udp_probe.py: `rotate_source_ports(..., deadline=None)`; `probe_all` dan
  `probe_dns` meneruskan `deadline`.
- tools/verify_udp_reflection.py (baru, 40 cek): A builder paket (struktur byte, mapping
  qtype, mode NTP, SSDP), B rasio amplifikasi lewat UDP server lokal (25 -> 185 byte = 7,4x),
  C reflection_capable + pagar budget, D checksum IP & header UDP + bentuk keluaran
  probe_spoof, E wiring endpoint, F panggilan NYATA rotate_source_ports & probe_all.
- docs/INVENTARIS.md: item 13 -> SELESAI.

## Catatan proses (jujur)
Tiga cek pertama merah karena asumsi verifier, bukan kode: (1) `probe_ntp` lupa ikut
diturunkan sehingga masih menang di `max()`; (2) `budget=0.2` berada PERSIS di ambang
`lewat()` karena floor budget = ambang = 0.2, jadi tahap pertama bergantung pembulatan
float; (3) karena itu tahap pertama memakai fungsi nyata dan mengukur amplifikasi DNS TXT
10,0x. Asersi diperbaiki agar mengunci yang memang deterministik (empat tahap terakhir).

## Data terukur
- UDP lokal: 25 byte -> 185 byte = 7,4x (deterministik, dipakai sebagai pengunci)
- DNS TXT nyata: ~10,0x (teramati saat menjalankan verifier)

## Bukti
- tools/verify_udp_reflection.py: .out/HASIL-107-verifier.txt
- make gate + make test: .out/HASIL-107-gate.txt, .out/HASIL-107-test.txt
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
