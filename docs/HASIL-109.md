# HASIL-109 — jalur raw spoof diperbaiki (item 13 lanjutan)

STEP: 109 — Item: 13, bagian spoof_src yang ternyata belum benar-benar jalan.

## Dua bug yang hanya muncul saat jalur ter-wire DIJALANKAN
1. `_ip_udp()` memack `ip_len`/`ip_off` dengan `"!"` (network byte order). BSD/macOS
   mengharuskan HOST byte order saat `IP_HDRINCL` aktif; Linux mengharuskan network order.
   Akibatnya `sendto()` selalu EINVAL di macOS. Bukti pemisah: tanpa HDRINCL kirim OK,
   dengan HDRINCL gagal - jadi bukan socket, bukan bind, bukan checksum (checksum 0xFFFF).
2. `probe_spoof()` memakai `gethostbyname(gethostname())` sebagai sumber paket; di mesin ini
   hasilnya 127.0.0.1, sehingga balasan untuk paket bersumber palsu tidak kembali lewat en0.
   Diganti `_local_ip()` (route lookup via UDP connect) dengan fallback.

## Catatan proses
Percobaan patch pertama gagal dua kali karena anchor: (a) `import sys` tidak ada di modul itu,
padahal konstanta baru memakai `sys.platform` - diganti `os.uname().sysname`; (b) helper
`_local_ip` sendiri memuat `gethostbyname(gethostname())` sebagai fallback, sehingga kalau
substitusi dijalankan SESUDAH penyisipan helper, fallback itu ikut berubah dan terjadi
rekursi. Urutan dibalik: substitusi dulu, sisipkan helper kemudian.

## Yang diubah
- backend/udp_probe.py: `IPLEN_ORDER` (host order di BSD/macOS, network order di Linux);
  `_ip_udp` memack panjang/fragmen sesuai platform; `_local_ip()` baru.
- tools/verify_udp_reflection.py: cek D sadar platform + cek urutan ip_len (tanpa ini
  verifier akan salah di macOS dan benar di Linux).

## Bukti
- Uji pemisah sudo (network vs host order, 3 sumber): keluaran bagian 2
- tools/verify_udp_reflection.py: .out/HASIL-109-verifier.txt
- make gate + make test: .out/HASIL-109-gate.txt, .out/HASIL-109-test.txt
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
