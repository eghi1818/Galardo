# HASIL-144 — gateway didaftarkan ke engine saat start

- tanggal: 2026-10-24 12:12
- catatan zsh: blok sebelumnya gagal total dengan 'zsh: event not found' (bang-history zsh mengekspansi tanda seru walau di dalam kutip ganda). Blok ini memakai setopt no_bang_hist + unsetopt nomatch.
- api.py: blok GALARDO_GATEWAY_BOOT - kalau GALARDO_GATEWAY_URL diisi, gateway didaftarkan ke proxypool saat start; kalau kosong cetak pesan dan lanjut
- bukti tanpa kredensial: app dijalankan dengan GALARDO_GATEWAY_URL=user:rahasia@127.0.0.1:9999 (lihat .out/STEP-144-fake.log)
- verify_gateway: +1 cek sumber = 28 cek
- gateway rc=0 | egress rc=0 | test rc=0 | gate rc=2
