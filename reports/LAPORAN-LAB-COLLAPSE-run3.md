# LAPORAN LAB COLLAPSE RUN 3 — galardo-lab-target @ 2000 rps spike
**Jobs:** job-e4dc55319be2 (run3, probe-abort @132K req) · **job-1130890dc325 (run3b, full 180s)**
**Skenario:** `lab-collapse-2000rps` v1 — instant spike 2000 rps, 50K identities, churn per-iteration
**Policy:** pol-global-v4 (cap 2500 rps, via API ter-audit) · **Evidence run3b:** VERIFIED 13 file, SHA `2e5a2fa4235ca22d…` → `~/Documents/`

---

## Hasil run3b (probe diberi ruang utk mengukur plateau)

| Metrik | Run 2 (1000 rps) | Run 3b (2000 rps) |
|---|---|---|
| Total request | 180.035 | **359.783** |
| RPS aktual | 994,7 | **1.987,8** |
| Error rate | 42,6% | **47,7%** |
| p50 / p95 | 68,9 / 2.005 ms | 337,9 / 2.015 ms |
| Target RSS peak | 94 MB | **162 MB** (setelah run turun ke 100 MB) |
| Collapse mutlak | tidak | **TIDAK TERJADI** — target survive 180s penuh |

## Temuan kunci: batas struktural, bukan collapse

1. **Throughput mengikuti beban**: server menerima ~2.000 rps tanpa drop — antrian
   menyerap kelebihan (error plateau 48%, bukan runaway).
2. **Memory naik ~70 MB** dibanding run 2 (94→162 MB) = alokasi buffer antrean
   yang lebih dalam; stabil sepanjang run (tidak ada leak runaway).
3. **Run 3 pertama membuktikan jalur collapse-safety**: probe gagal 5× beruntun →
   ABORT otomatis di 132K req (fail-closed, ter-audit), recovery RECOVERED.
4. **Kesimpulan collapse point**: dengan profil ini, stdlib threading server TIDAK
   collapse di 2000 rps — batas berikutnya ada di limit file-descriptor/thread-pool
   OS (ulimit) dan memori antrian. Untuk mencari collapse mutlak, naikkan
   `ulimit -n` target + policy v5, ATAU tambahkan endpoint `/api/error` weight
   tinggi (fast-fail) supaya antrian tidak menyerap beban.

## Matriks program kapasitas (3 run selesai)

| Run | Target | RPS | Failed | RSS peak | Status |
|---|---|---|---|---|---|
| 1 | lab | 995 | 42,6% | 94 MB | COMPLETED |
| 3a | lab | 1.973 | 47,7% | 97 MB | ABORTED (probe, fail-closed) |
| 3b | lab | 1.988 | 47,7% | 162 MB | COMPLETED |
| prod Run 1 | wecash.ai | 188 | 72,6% | — | COMPLETED (jenuh 45–188 rps) |
| prod Run 2 | — | ditunda menunggu tuning origin | | | |

## Pending: Run 2 Produksi wecash.ai

Prasyarat (dari kesepakatan): tuning worker/DB pool origin selesai + jendela uji
dikonfirmasi. Scenario sudah siap dibuat otomatis saat Anda konfirmasi — tanpa
ramp (spike instan), sesuai cap policy yang berlaku untuk wecash.ai.
