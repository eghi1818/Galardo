# HASIL-68 - bus NATS opt-in (item 9 / Tier 2, bagian 1)

- Status : SELESAI
- Sifat  : kode + infra
- Isi    : backend/bus.py (publish fail-open, subject galardo.events.<tipe>, stats),
           webhooks.fire() menerbitkan event ke bus, service nats di docker-compose,
           tools/verify_bus.py (17 tes offline)
- Keputusan: NATS aktif TAPI opt-in via GALARDO_NATS_URL; polling tetap default.
  Ini menjawab pertanyaan terbuka di docs/SERVER-SPEC.md
- Fail-open: broker mati tidak menghalangi; stat failed + last_error tercatat
- Verifikasi: verify_bus 17/17, verify_compose hijau, compose config VALID, make test hijau
