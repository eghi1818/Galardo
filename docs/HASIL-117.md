# HASIL-117 — L2: Galardo jalan sebagai container

- tanggal: 2026-10-22 14:41
- image: galardo:local ; orkestrasi: docker compose
- bukti: /api/v1/health -> 200 dari container, / -> 200
- docker: Docker version 29.8.2, build 7fc2dff

## Catatan
- App lokal (Mode Aktif) dimatikan lebih dulu agar port 8090 bebas.
- Cara naik/turun: make docker-up / make docker-down.
