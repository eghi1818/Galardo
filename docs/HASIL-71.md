# HASIL-71 - klien PostgreSQL minimal (item 9 / Tier 2, bagian 4)

- Status : SELESAI
- Sifat  : kode + infra
- Isi    : backend/pg.py (wire protocol v3, auth trust/cleartext/md5/scram-sha-256,
           simple query, parsing RowDescription/DataRow/ErrorResponse),
           service pg di compose (postgres:16-alpine, healthcheck, volume pgdata),
           tools/verify_pg.py (29 tes offline)
- Keputusan: opsi (a) klien minimal - konsisten stdlib, tanpa dependensi
- Uji live: connect ke postgres:16 via scram-sha-256, create/insert/select BERHASIL
- F-13: startup packet kurang byte terminator -> PostgreSQL menolak "invalid startup packet
  layout: expected terminator as last byte". Klaim 'berhasil' sempat salah di commit 11efe01;
  diperbaiki + cek terminator ditambahkan ke verify_pg.
- Fail-open: GALARDO_PG_DSN kosong -> tidak aktif; error query tidak melempar
- Verifikasi: verify_pg 29/29, verify_compose hijau, compose config VALID, make test hijau
