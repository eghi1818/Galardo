# HASIL-110 — spoof sumber terbukti; penerima raw diganti UDP (item 13)

STEP: 110 — Item: 13, penutup jalur spoof_src.

## Temuan
Uji pemisah dengan sudo membuktikan paket bersumber palsu SUDAH bekerja sejak perbaikan
IPLEN_ORDER + _local_ip:

    kontrol UDP biasa : BALASAN 25 byte
    raw->raw          : paket=0            (raw socket macOS BUTA)
    raw->udp listen   : BALASAN 25 byte | qid_cocok=True
    raw+udp csum      : BALASAN 25 byte | qid_cocok=True

Jadi yang rusak hanya cara menerima. Raw socket AF_INET/SOCK_RAW/IPPROTO_UDP di macOS
tidak melihat balasan UDP sama sekali - dan `probe_spoof` juga tidak pernah memanggil
bind, jadi ini bukan soal bind.

## Yang diubah
- backend/udp_probe.py: `probe_spoof` tetap memakai raw untuk KIRIM (itu yang memungkinkan
  spoof sumber), tetapi menerima lewat UDP socket terikat ke (local, sport), dengan fallback
  ke raw bila port tidak bisa diikat. Bukti spoof tetap sah: balasan hanya bisa datang kalau
  server memakai IP sumber dari header kita.
- backend/udp_probe.py: perbaikan pendahulu `socket._local_ip()` -> `_local_ip()`. Regex
  penggantian sebelumnya menyisakan prefix `socket.`, dan AttributeError-nya tertelan
  `except Exception` sehingga jatuh ke sumber 0.0.0.0.
- tools/verify_udp_reflection.py: 3 cek pengunci (pakai _local_ip, penerima UDP terikat
  sport, IPLEN_ORDER dipakai di header).

## Bukti
- Uji sudo: keluaran bagian 2 (termasuk diagnostik bind raw)
- tools/verify_udp_reflection.py: .out/HASIL-110-verifier.txt
- make gate + make test: .out/HASIL-110-gate.txt, .out/HASIL-110-test.txt
