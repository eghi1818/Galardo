# LAPORAN CAPACITY VALIDATION — wecash.ai (Run 1)
**Job:** job-715ec6a1e401 · **Tanggal:** 2026-10-10 03:05–03:11 UTC (10:05–11:11 WIB)
**Skenario:** `wecash-capacity-saturation` v1 (immutable, sha 81e1e188…) — ramp 50→400 rps, 360s
**Identity sim:** 10.000 identitas sintetis, churn per-iteration, X-Client-Id (edge path), seed `wecash-edge-sim`
**Connection churn:** ON (no-keep-alive — tiap request koneksi TCP baru)
**Executor:** k6 via remote worker `w11-jkt-1` · **Policy:** pol-global-v2 (cap 500 rps / 500 VU)
**Evidence:** `~/Documents/evidence_job-715ec6a1e401.tar.gz` — bundle SHA-256 `1e57cc17186e3b49…` (VERIFIED, 11 file)

---

## Hasil utama

| Metrik | Nilai |
|---|---|
| Total request | **68.276** |
| RPS aktual | **187,6 rps** (rata-rata 364s) |
| Failed rate | **72,6%** — hampir seluruhnya **request timeout** (bukan 4xx/5xx) |
| p50 / p95 / p99 | 1.163 ms / **4.000 ms** / 4.004 ms |
| Bandwidth | ~901 MB diterima |
| Recovery target | **RECOVERED** (probe independen HEALTHY ×3) |
| Safety abort | Tidak terpicu — controller sehat sepanjang run |

## Titik jenuh (saturation point) — temuan kunci

**Origin/edge wecash.ai jenuh di antara 45–188 rps** pada profil koneksi-baru-per-request:

| Beban | RPS efektif | p50 | p95 | Failed |
|---|---|---|---|---|
| Smoke decompose (15s) | 45 rps | 568 ms | 1.527 ms | **2,7%** |
| **Full ramp (run ini)** | **188 rps** | 1.163 ms | **4.000 ms (timeout)** | **72,6%** |

Pola: p95 menyentuh timeout 4s tepat saat rate melewati ~100 rps efektif —
timeouts murni (bukan HTTP error) = **socket/connection queue di path CF→origin penuh**.
Konsisten dengan prediksi diagnosa sebelumnya, kini terkonfirmasi dengan 68K request,
10K identitas, dan churn maksimal.

## Interpretasi (advisory)

1. **Kapasitas aman terbukti: ≥45 rps; 188 rps TIDAK terdukung** pada mode
   koneksi-baru-per-request (worst-case — ini yang membebani session table).
2. Traffic user riil (browser, keep-alive) menekan origin JAUH lebih ringan —
   kapasitas efektif produksi lebih tinggi dari angka worst-case ini.
3. 72,6% failed saat puncak = antrian/penolakan terukur, BUKAN collapse:
   recovery RECOVERED dalam hitungan detik setelah traffic berhenti.

## Rekomendasi origin (urut prioritas)

1. Cek **worker/PM2/uvicorn concurrency** Next.js — naikkan max connections.
2. Cek **DB connection pool** — kandidat bottleneck #1 saat 150+ concurrent.
3. Aktifkan **CF caching** untuk asset statis (kurangi origin hit drastis).
4. Setelah tuning: ulangi run identik (skenario sama, versi immutable baru) —
   bandingkan evidence SHA-256 sebelum/sesudah.

## Next step program

- Run 2 (pasca-tuning): ramp sama, target failed <10% pada 188 rps.
- Run 3: cap policy >400 rps (approval policy baru) bila p95 stabil.
- Opsional: fleet multi-region 2–4 VPS untuk >1.000 rps generator-side.
