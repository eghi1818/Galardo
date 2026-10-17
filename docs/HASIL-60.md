# HASIL-60 - kartu Bukti & observer di halaman live (irisan 3/6 item 7)

- Status : SELESAI (verifikasi visual di browser oleh operator)
- Sifat  : kode; dashboard/index.html
- Celah ditutup: GET /test-jobs/*/down, GET /test-jobs/*/telemetry,
                 POST /test-jobs/*/observer, POST /test-jobs/*/reconcile
- Isi    : kartu di halaman live: snapshot down/observer/probe apa adanya, telemetry mentah,
           tombol Jalankan observer / Reconcile / Muat ulang
- Tidak disentuh: RENDER.live yang sudah ada, RENDER.evidence (bundle + verify hash + download)
- Catatan 1: traceback ConnectionResetError di output make test = noise normal (tertangkap)
- Catatan 2: gate diperbaiki - cari baris RESULTS + cetak 15 baris terakhir bila gagal
- Catatan 3: F-1 ditutup di STEP-60b (kunci idempotency unik per-run)
