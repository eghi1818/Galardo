# TARGET BUKTI PERTAMA (V1.4)

Urutan yang WAJIB diikuti supaya "MATI" tidak jadi klaim:

1. Intel masuk -> POST /api/v1/intel/preflight (klaim = hipotesis, divergensi dicatat).
2. Kandidat origin -> GET /api/v1/origins/<domain> (putus rantai edge->origin).
3. Baseline saksi -> POST /api/v1/checkhost (3+ negara, sebelum serangan).
4. Ukur plafon -> make capacity / make capacity-fast (angka knee, jangan tembak buta).
5. Spike -> engine lewat lane (GALARDO_MULTILANE=1) + egress rotate.
6. Verdict -> POST /api/v1/verdict (mode + lapisan + niat) lalu POST /api/v1/falsify (uji pembantah).
7. Bukti -> POST /api/v1/bukti (entri ber-hash) -> docs/bukti/ledger.jsonl.
8. Laporan: mode, lapisan, niat, 3 saksi, TTF/TTR, hash. Kalau ragu -> tulis belum_konklusif.

Target: wecash.ai, waspadaweb.com. KPI: MATI LUMPUH TOTAL (bukan throughput).
