# GALARDO — BASELINE KAPASITAS MESIN & TARGET

Diukur 2026-10-15 di MacBook (M-series, 32 GB) memakai `make capacity`.
Angka ini **wajib** dibaca sebelum menyimpulkan "target kuat" atau "target lemah".

---

## 1. Plafon GENERATOR (alat ukur = laptop ini)

Perintah: `GALARDO_CAP_STEPS=5,10,20,40,80 python3 tools/galardo_capacity.py`
(rute `/healthz`, target tanpa plafon)

| VUs | rps | p50 ms | p95 ms |
|---|---|---|---|
| 5 | 5.598 | 0,7 | 1,3 |
| 10 | 5.871 | 1,2 | 2,8 |
| 20 | 5.900 | 2,4 | 6,7 |
| 40 | 5.834 | 4,7 | 13,8 |
| 80 | 5.961 | 9,4 | 25,9 |

**Plafon generator ≈ 5.900 rps** untuk rute tanpa latency.

Artinya: **rps di atas ~5.900 tidak bisa dicapai laptop ini**, walau VU ditambah.
Kalau target lebih cepat dari itu, laptop jadi bottleneck dan hasilnya menyesatkan.

## 2. Plafon TARGET (contoh: 16 worker, `/api/heavy` 150 ms)

Perintah: `GALARDO_CAP_WORKERS=16 GALARDO_CAP_PATH=/api/heavy ...`

| VUs | rps | p50 ms | p95 ms |
|---|---|---|---|
| 5 | 25,9 | 155 | 157 |
| 10 | 52,9 | 155 | 157 |
| 20 | 85,3 | 158 | 302 |
| 40 | 89,4 | 418 | 460 |
| 80 | 93,9 | 769 | 1.225 |

**Plafon target ≈ 94 rps.** Teoretis 16 worker / 0,15 s = 106 rps — cocok.
p95 meledak mulai 40 VU: itu tanda antrian, bukan tanda target mati.

## 3. Aturan keputusan

| Kondisi | Tindakan |
|---|---|
| Plafon target **jauh di bawah** plafon generator | laptop cukup; tidak perlu VPS |
| Plafon target **mendekati/melebihi** 5.900 rps | perlu generator kedua: VPS atau k6 |
| Knee tidak ketemu sama sekali | target tanpa plafon -> pasang `/control/capacity` dulu |
| rps flat sejak langkah pertama | rampa mulai terlalu tinggi -> turunkan VU awal |

## 4. Batas yang harus jujur diakui

- Angka di atas berlaku untuk **rute ringan** dan **localhost** (tanpa latency jaringan).
- Target di internet menambah RTT; plafon generator akan turun sebanding.
- Plafon generator bergantung pada beban mesin lain (browser, IDE, dsb).
- Untuk target >5.900 rps, hasil dari laptop ini **bukan** kapasitas target.
