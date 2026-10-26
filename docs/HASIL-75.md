# HASIL-75 — F-7: probe UDP tak berpagar waktu (endpoint /sources/*/udp)

Status: TUTUP.

## Temuan
`probe_all()` menjalankan 5 tahap jaringan berurutan tanpa batas waktu total:
probe_dns_best (loop atas beberapa kandidat qname/qtype), probe_ntp (loop atas server),
probe_ssdp (window), rotate_source_ports (n port). Dengan timeout per-iterasi 2-3 s,
worst case jauh di atas timeout klien 15 s -> suite crash (tes lalu dipaksa timeout=45).
Ini juga akar F-1b: preflight menunggu timeout probe.

## Perbaikan (membatasi, bukan mengubah semantik)
- `probe_all(..., budget=None)`: pagar waktu TOTAL, default env GALARDO_UDP_BUDGET atau 8.0.
  Tahap yang tak sempat berjalan ditandai {"skipped": "budget"} - BUKAN dianggap gagal.
- `deadline` disebarkan ke dalam loop fan-out: `_probe_many`, `probe_dns_best`, `probe_ntp`,
  `probe_dns` (guard `>= deadline` + break).
- Timeout per-target dibatasi sisa deadline (`min(timeout, deadline - time.time())`)
  sehingga satu target tak bisa menembus pagar.
- Endpoint `/sources/*/udp`: meneruskan `budget` dari body atau env; `probe_spoof`
  dibatasi timeout (default 5 s, dapat diatur via `spoof_timeout`).
- Hasil kini memuat `budget`, `elapsed`, `skipped` (terlihat dan dapat diuji).

## Bukti
    budget=3.0  -> detik 3, elapsed 3.0, skipped ['ntp_mode6','ssdp','port_rotation']
    budget=6.0  -> detik 6, elapsed 6.0, skipped ['ssdp','port_rotation']
    sebelumnya: menembus 15 s (klien mati di tengah)
    verify_udp_budget.py -> 16 passed, 0 failed (3x berturut)
    make test -> 79 passed, 0 failed
    verify_netssl_wired -> 20/0 ; verify_devup -> 2/2

## Catatan
`elapsed` menyentuh `budget` memang disengaja: probe memakai anggaran seproduktif
mungkin, yang penting tidak MELEBIHI. Yang gagal-keras sebelumnya adalah ketiadaan batas.

## Insiden kecil (jujur)
Dua percobaan pertama gagal menulis: (a) regex `[^)]*` berhenti di `)` pertama sehingga
`budget` jadi keyword argumen `dict.get` -> TypeError (tertangkap 2 tes gagal);
(b) script patch mati StopIteration karena `probe_ntp` tak punya loop `for`.
Keduanya ditutup dengan penjaga AST (`dict.get` tanpa keyword) dan patch tahan-fungsi.
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
