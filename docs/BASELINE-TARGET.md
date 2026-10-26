# BASELINE-TARGET - saksi per-negara (check-host.net)

- tanggal: 2026-10-26 15:30
- alat: tools/checkhost.py (check-host.net), 4 node, batas 12s
- status: titik nol SEBELUM spike; pembanding saat target ditekan

## wecash.ai
```
url: https://wecash.ai
catatan: sebagian (batas waktu tercapai)
  in   India          ?        belum siap
  ir   Iran           ?        belum siap
  se   Sweden         ?        belum siap
  sg   Singapore      ?        belum siap
VERDICT: belum ada hasil
```

## waspadaweb.com
```
url: https://waspadaweb.com
catatan: sebagian (batas waktu tercapai)
  ch   Switzerland    ?        belum siap
  de   Germany        ?        belum siap
  ir   Iran           ?        belum siap
  sg   Singapore      ?        belum siap
VERDICT: belum ada hasil
```

## Catatan
- Kedua target di belakang Cloudflare (104.21.x / 172.67.x) sehingga volume mentah ke edge
  mudah diserap; tekanannya harus diarahkan agar sampai ke origin (path tidak di-cache /
  cache-buster) dan dari banyak IP.
- Kalau saat spike node mulai tanda ? atau MATI, itu saksi kedua yang sah.
