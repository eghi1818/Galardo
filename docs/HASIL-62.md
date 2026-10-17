# HASIL-62 - editor probe-contract di tabel Targets (irisan 5/6 item 7)

- Status : SELESAI (verifikasi visual di browser oleh operator)
- Sifat  : kode; dashboard/index.html (JS ditulis via /tmp/pc.js)
- Route  : POST /targets/*/probe-contract
- Isi    : tombol "Kontrak" di kolom aksi tiap target membuka editor
           (url, expected_status, interval_sec, timeout_sec, failure_threshold)
- Catatan: field kosong tidak dikirim; angka non-numerik diabaikan; hasil tampil apa adanya
- Catatan: probe_contract sudah tampil read-only sebelumnya, kini bisa diubah dari UI
