# HASIL-99 — P5 TUTUP: koherensi db multi-proses

STEP: 99 — Item: P5 (docs/PENDING.md).

## Celah yang ditutup
`_state_mtime = float("inf")` dipakai sebagai penanda "cermin JSON bukan sumber", tetapi
cabang reload cermin dijaga `_state_mtime != float("inf")` sehingga TIDAK PERNAH jalan di
mode PG. Akibatnya proses kedua di mode PG tidak pernah melihat tulisan proses pertama.

## Yang diubah
- `backend/db.py`: helper `_mirror_mtime()` (mtime ns cermin, 0.0 bila belum ada).
  Sentinel `inf` dibuang dari `_load()` dan `_save()`.
- Deteksi perubahan: mtime cermin naik -> mode JSON membaca ulang cermin; mode PG
  memanggil `db_pg.hydrate()` (sumber kebenaran tetap PG), dengan cermin sebagai fallback
  bila hydrate gagal.
- Verifier baru `tools/verify_pg_multiproc.py`: dua proses nyata (pembaca memuat state
  lebih dulu, penulis lain menulis, pembaca wajib melihat), plus simulasi mode PG tanpa
  PG hidup, plus cek sentinel inf sudah hilang.

## Bukti
- `tools/verify_pg_multiproc.py`: lihat .out/HASIL-99-verifier.txt
- `make gate` + `make test`: lihat .out/HASIL-99-gate.txt dan .out/HASIL-99-test.txt

## Sisa (langkah berikut, belum dikerjakan)
- STEP-100: tabrakan nama env P2. `proxypool.resolve()` membaca `GALARDO_PROXY_<NAMA>`
  dan mewajibkan `host:port`, sedangkan provider memakai `GALARDO_PROXY_URL/_KEY/_AUTH/`
  `_POOL/_TTL/_TIMEOUT`. Nama pool `url`/`key`/`auth`/`pool`/`ttl`/`timeout` menabrak.
- STEP-101: rekonsiliasi dokumen — kolom/bagian status PENDING, ROADMAP:155, backfill
  STEPLOG 81-96 dari commit 58d8261..3f64fd9, `EMERGENCY.md` (acuan make test 61 -> 79),
  dan `gate.yml` yang tidak memasang node sehingga `node --check` di-skip di CI.
- P1 belum bisa disebut tutup: run hijau di tab Actions belum dikonfirmasi (`gh` absen).
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
