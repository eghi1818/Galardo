# LAPORAN PRODUCTION RUN 2 — wecash.ai (post-tuning validation)
**Job:** job-67aadcda2bab · 2026-10-10 09:37–09:41 UTC (16:37–16:41 WIB)
**Skenario:** `wecash-prod-run2-spike` v1 — **spike instan tanpa ramp**, cap 400 rps, 180s
**Identity sim:** 10.000 identitas (seed wecash-edge-sim), churn per-iteration (X-Client-Id, edge path)
**Executor:** k6 via remote worker `w11-jkt-1` · Policy: pol-global-v2 (cap 500 rps)
**Evidence:** `~/Documents/evidence_job-67aadcda2bab.tar.gz` — VERIFIED 11 file, bundle SHA `0d43b8c671e073ec…`

---

## Hasil

| Metrik | Run 1 (ramp, pra-tuning) | **Run 2 (spike, pasca-tuning)** |
|---|---|---|
| Total request | 68.276 | **69.746** |
| RPS | 188 | **379** (spike instan) |
| Failed rate | 72,6% | **96,2%** |
| p50 / p95 | 1.163 / 4.000 ms | n/a (median failed=0) / 4.000 ms |
| Bandwidth | ~901 MB | ~288 MB |
| Recovery | RECOVERED | **RECOVERED** |

## Interpretasi

1. **Spike instan 2× lipat rate produksi → kegagalan meluas (96,2%)** — tanpa
   periode pemanasan, koneksi langsung membanjiri antrian; p95 = timeout 4s.
2. **Bandwith turun (901→288 MB)**: lebih sedikit respons sukses yang selesai —
   mayoritas koneksi mati di antrian sebelum data mengalir.
3. **Recovery tetap cepat & bersih** (RECOVERED): tidak ada collapse persisten.
4. Perbandingan ini MEMBUTUHKAN satu catatan: Run 1 ramp vs Run 2 spike bukan
   A/B yang setara — profil beban berbeda. Untuk mengukur efek tuning origin
   secara adil, jalankan **Run 2b: ramp identik Run 1** (skenario
   `wecash-capacity-saturation`, immutable) — angkanya akan comparable 1:1.

## Kesimpulan sementara & langkah

- Spike 379 rps tanpa warm-up masih menembus batas nyaman origin.
- Jika tuning memang sudah naik, Run 2b (ramp) seharusnya menunjukkan failed
  jauh di bawah 72,6% pada 188 rps — ini uji yang menentukan.
- Platform siap: skenario immutable sudah ada, cukup konfirmasi jendela uji.

*Dibuat otomatis oleh Galardo — evidence + audit trail tersedia.*
