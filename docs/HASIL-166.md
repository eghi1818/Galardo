# HASIL-166 - transport lane dinyalakan (fix merah STEP-165)

- tanggal: 2026-10-24
- MERAH STEP-165: "dengan 2 lane: tetap melayani" gagal (0 request), sementara lane ber-endpoint
  (set_proxy) justru jalan -> akarnya INISIALISASI transport, bukan lane/sebaran.
- FIX: helper _start_lane(tr) yang meniru metode transport utama (start/open/warmup/connect, nama
  dicari bukan ditebak), dipanggil pada jalur lane TANPA endpoint; jalur ber-endpoint tetap set_proxy.
  Verifier juga ditambah diagnosa (window/errors) + cek kesiapan transport lane.
- angka: ml rc=0 | knee rc=0 | live rc=0 | ch rc=0 | pages rc=0 | test rc=0 | gate rc=0
