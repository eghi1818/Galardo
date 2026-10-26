# HASIL-58 - panel Ownership di dashboard (irisan 1 item 7)

- Status : SELESAI (verifikasi visual di browser oleh operator)
- Sifat  : kode; dashboard/index.html + tools/verify_dashboard_pages.py
- Isi    : halaman Ownership (nav + PAGE_TITLES + RENDER.ownership) menampilkan level
           kepemilikan per target dan tombol challenge + verify dns/file/echo/attest
- Route  : /targets, /targets/*/challenge, /targets/*/ownership,
           /targets/*/verify/{dns,file,echo,attest}
- Verifier: tools/verify_dashboard_pages.py (nav <-> PAGE_TITLES <-> RENDER konsisten)
- Catatan: UI tanpa harness tes otomatis; verifikasi panel manual di browser

## Penerimaan (bukti live)
- POST /targets/tgt-lab/challenge -> 201 record_name+expected_value+instructions
- POST /targets/tgt-lab/verify/attest -> verified=true level=1 is_proof=false
- GET  /targets/tgt-lab/ownership -> status=VERIFIED ownership_level=1 proof terisi
- Catatan: Verify DNS tidak berlaku untuk domain 127.0.0.1 (butuh zona publik); pakai koler.space.
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
