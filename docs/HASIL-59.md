# HASIL-59 - panel Sources (irisan 2/6 item 7)

- Status : SELESAI (verifikasi visual di browser oleh operator)
- Sifat  : kode; dashboard/index.html
- Isi    : halaman Sources: daftar sumber + registrasi + probe/udp/hapus + matrix + pick + sample identity pool
- Route  : GET /sources, POST /sources, POST /sources/*/{probe,udp,remove}, GET /sources/matrix, POST /sources/pick, GET /identity-pool
- Verifier: tools/verify_dashboard_pages.py (nav <-> PAGE_TITLES <-> RENDER) + node --check

## Penerimaan (bukti live)
- POST /sources -> 201 id=src-uji-59
- POST /sources/src-uji-59/probe -> 200 proven=[http1,keepalive,tls12] unproven=[ipv6] na=[http2,tls13,tls13_lib] + evidence per kapabilitas
- POST /sources/src-uji-59/remove -> {"removed":"src-uji-59"}
- GET /identity-pool?count=8 -> count/pool_sha256/bucket_counts/entropy/sample terisi
- Catatan: ID sumber berpola src-<label>; panel memakai s.id sehingga tepat.
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
