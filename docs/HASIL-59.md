# HASIL-59 - panel Sources (irisan 2/6 item 7)

- Status : SELESAI (verifikasi visual di browser oleh operator)
- Sifat  : kode; dashboard/index.html
- Isi    : halaman Sources: daftar sumber + registrasi + probe/udp/hapus + matrix + pick + sample identity pool
- Route  : GET /sources, POST /sources, POST /sources/*/{probe,udp,remove}, GET /sources/matrix, POST /sources/pick, GET /identity-pool
- Verifier: tools/verify_dashboard_pages.py (nav <-> PAGE_TITLES <-> RENDER) + node --check
