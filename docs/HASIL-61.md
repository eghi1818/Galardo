# HASIL-61 - halaman Overrides di dashboard (irisan 4/6 item 7)

- Status : SELESAI (verifikasi visual di browser oleh operator)
- Sifat  : kode; dashboard/index.html (JS panel ditulis via /tmp/ovr.js)
- Route  : POST /overrides, GET /overrides, POST /overrides/*/probe, POST /overrides/*/revert
- Isi    : form buat override (domain, paths, mode 404/blank/410/503, shim_port, note, path probe),
           tabel override aktif + tombol Probe & Revert, kotak hasil apa adanya
- Bukti  : panel menampilkan forced + override_header dari probe, bukan sekadar status
- Catatan: editor probe-contract (POST /targets/*/probe-contract) belum disambungkan - kandidat STEP-62
- Catatan: heredoc bersarang pernah membuat terminal macet; JS kini ditulis ke file dulu
