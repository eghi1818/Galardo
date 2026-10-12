# LAPORAN MAX SPIKE — wecash.ai via bit.ly target (job-a1613e367eb7)
**2026-10-12 08:38–08:42 UTC** · **Skenario:** `wecash-max-spike-bitly` v1 — spike instan 500 rps, 180s
**Identity sim:** 10.000 (seed wecash-edge-sim), churn per-iteration · **Executor:** k6 @ w11-jkt-1
**Target path:** bit.ly/4epTj6g → http://wecash.ai/ → Cloudflare → origin
**Evidence:** `~/Documents/evidence_job-a1613e367eb7.tar.gz` — VERIFIED 11 file, SHA `9894fa3c5234c733…`

## Hasil

| Metrik | Nilai |
|---|---|
| Total request | **83.283** |
| RPS aktual | **452,8** (spike instan, 184s) |
| Failed rate | **92,4%** (timeout 4s — koneksi dibuang di antrian) |
| p50 / p95 | n/a (median failed=0) / 4.000 ms |
| Bandwidth | ~318 MB |
| Recovery | RECOVERED |

## Perbandingan lintas run produksi (profil churn/no-keep-alive)

| Run | Beban | RPS aktual | Failed |
|---|---|---|---|
| Run 1 (ramp) | cap 400 | 188 | 72,6% |
| Run 2 (spike) | cap 400 | 379 | 96,2% |
| **Run MAX (spike)** | **cap 500** | **453** | **92,4%** |

## Kesimpulan

1. **Konsisten: origin jenuh di ~180–450 rps mode churn** — naikkan beban, failed
   tetap 92–96% (bukan naik terus). Target TIDAK down: respons 200 tetap mengalir
   untuk request yang dilayani, recovery RECOVERED setelahnya.
2. **Bukan bandwidth** (318 MB / 3 menit = ~14 Mbps — kecil), melainkan
   **socket/connection handling di path CF→origin** saat koneksi baru per request.
3. Mode keep-alive (traffic user riil) berbeda — lihat smoke p95 737ms @ 41 rps.
4. Catatan k6 v2: p50 tercatat 0 bila >50% sample failed (median dari failed
   request yang tidak masuk distribusi duration) — gunakan avg/p95 untuk baca.

## Next yang tersedia

- Run dengan keep-alive (tanpa churn) pada 500 rps → memisahkan "kegagalan karena
  koneksi baru" vs "kegagalan karena kapasitas respons".
- Multi-region fleet untuk menembus >500 rps dari generator.
