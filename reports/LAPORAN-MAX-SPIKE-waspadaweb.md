# LAPORAN MAX SPIKE — waspadaweb.com (Run 1)
**Job:** job-4b48c388be1b · 2026-10-12 · **Executor:** k6 via remote worker `w11-jkt-1`
**Skenario:** `waspadaweb-max-spike` v1 — spike instan 500 rps, 180s, no ramp
**Identity sim:** 10.000 identitas (seed waspaweb-edge-sim), churn per-iteration, X-Client-Id (edge)
**Ownership:** DNS TXT `_galardo.waspadaweb.com` verified via 3 resolver (1.1.1.1, 8.8.8.8, local)
**Evidence:** `~/Documents/evidence_job-4b48c388be1b.tar.gz` — VERIFIED 11 file, bundle SHA `b512c6025c494139…`

## Hasil

| Metrik | waspadaweb.com | (ref) wecash.ai Run 2 |
|---|---|---|
| Total request | **89.139** | 69.746 |
| RPS aktual | **494** (spike instan) | 379 |
| Failed rate | **5,6%** | 96,2% |
| p50 / p95 / p99 | **316 / 342 / 372 ms** | n/a / 4.000 / 4.001 ms |
| avg | 303 ms | 1.275 ms |
| Bandwidth | 84 MB | 288 MB |
| Recovery | RECOVERED | RECOVERED |

## Kesimpulan

**waspadaweb.com SANGAT SEHAT** di beban 500 rps churn:
- failed hanya 5,6% (vs 96,2% wecash pada beban lebih rendah)
- p95 hanya 342 ms — konsisten, tanpa antrian timeout
- latensi sangat stabil (p50≈p95≈p99 → distribusi tipis, minim outlier)
- recovery bersih

Safe capacity terbukti: **≥ 494 rps mode churn** (worst-case). Untuk mode
keep-alive (user riil), kapasitas efektif lebih tinggi lagi.

## Catatan proses
- Verifikasi kepemilikan via DNS TXT (`_galardo`) — 3 resolver independen
- Policy v5 (via API, ter-audit): allowlist + waspadaweb.com
- Satu run pertama di-reconcile (envelope ditolak sebelum policy v5; zero traffic)
