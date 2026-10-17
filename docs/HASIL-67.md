# HASIL-67 - Docker Compose (item 8 / Tier 1, bagian 4) - ITEM 8 TUTUP

- Status : SELESAI
- Sifat  : kode infra; Dockerfile, docker-compose.yml, .dockerignore, tools/verify_compose.py
- Perubahan kode: run_local.py bind host dari GALARDO_BIND (default tetap 127.0.0.1)
  supaya port mapping Docker tembus tanpa mengubah perilaku lokal
- Isi compose: satu service, port 8090/8095/8899, volume ./data, env_file .env opsional,
  restart unless-stopped, healthcheck ke /api/v1/health
- Perintah: make docker-verify | docker-build | docker-up | docker-down
- Verifikasi: verify_compose 20/20, docker compose config VALID, build + up + health 200 + down
- Catatan: port 8090 bentrok dengan make dev-up; hentikan dev-up dulu sebelum docker-up
