# HASIL-70 - ekspor OTLP/HTTP JSON (item 9 / Tier 2, bagian 3)

- Status : SELESAI
- Sifat  : kode + infra
- Isi    : backend/otlp.py (payload OTLP JSON: resourceMetrics + resourceSpans, tanpa protobuf),
           ekspor dipanggil di orchestrator setelah final_metrics ditulis,
           ops/otel-collector.yaml, service otel di docker-compose, tools/verify_otlp.py (31 tes)
- Prinsip: opt-in via GALARDO_OTLP_URL; tanpa itu -> no-op. Fail-open: error tidak menghalangi job.
- Tanpa dependensi: memakai netssl.context() + urllib, payload JSON
- Verifikasi: verify_otlp 31/31, verify_compose hijau, compose config VALID, make test hijau
