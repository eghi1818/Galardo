# HASIL-72 — Adapter db -> PostgreSQL dengan fallback JSON

Status: SELESAI — uji live hijau, fallback terbukti.

## Yang dibangun
- backend/db_pg.py: adapter PG untuk db.py. Tabel galardo_docs (collection,id,doc jsonb)
  dan galardo_audit (event_id,occurred_at,payload). Upsert idempotent
  (on conflict do update / do nothing), DDL create table if not exists.
- backend/db.py: saat GALARDO_PG_DSN ada DAN koneksi hidup -> hydrate dari PG,
  file JSON tetap ditulis sebagai cermin, 5 titik sinkron (insert/update/delete/
  audit/observation). Tanda tangan publik TIDAK berubah.
- Fail-open: error connect/DDL/query -> mode json, alasan dicatat di db.backend().
- db.all() alias list() (F-15); db.backend() status backend.

## Bukti uji live (PG 16.15, container)
    backend(): {'enabled': True, 'active': True, 'reason': 'aktif', 'mode': 'postgres'}
    BARIS DI PG: [{'collection': 'uji72', 'id': 'u1',
                   'doc': '{"id": "u1", "nama": "budi2", ...}'}]
    AUDIT DI PG: [{'event_id': 'aud-c39750ec9976', '?column?': 'uji72.create'}]
    setelah delete (harus 0): [{'count': '0'}]
    cermin audit.jsonl ada: True ; cermin state.json ada: True
    LIVE_PG_OK

## Bukti fallback (PG dimatikan)
    backend(): {'enabled': True, 'active': False,
                'reason': 'ConnectionRefusedError: [Errno 61] Connection refused', 'mode': 'json'}
    get via fallback: {'id': 'u9', 'nama': 'tetap-jalan'}
    FALLBACK_OK

## Gate
    tools/verify_db_pg.py -> RESULTS: 46 passed, 0 failed
    tools/verify_pg.py    -> RESULTS: 35 passed, 0 failed
    make test             -> 79 passed, 0 failed (jalur JSON tak berubah)

## Temuan yang lahir DAN ditutup di step ini
F-15 (P1) backend/rbac.py:45 memanggil db.all("users") padahal db.py tak punya all().
     Laten AttributeError. TUTUP: alias all(name, filt=None) -> list().
F-16 (P1) adapter db_pg membaca balikan query dengan bentuk salah. pg.PG.query()
     mengembalikan (rows, err) dan TIDAK melempar, jadi fail-open tak akan pernah
     aktif dan baris hasil terbaca sebagai [rows, None]. Ketangkap semata karena
     membaca bentuk balikan sebelum menulis tes; TIDAK ADA verifier yang menyentuh
     adapter saat itu. TUTUP: _rows() memeriksa err dan melempar; _ddl/_dicts/put/
     drop/audit memakainya; verifier menambah fake-conn untuk mengujinya.
F-17 (P1) db_pg.status() melaporkan _ready/_reason apa adanya tanpa memicu koneksi
     -> panggilan pertama selalu 'mode: json' walau PG hidup. Ketangkap oleh uji
     live, BUKAN oleh verifier offline (cek mode hanya saat DSN kosong).
     TUTUP: status() memanggil active(); verifier menambah 2 cek regresi.

## Catatan desain
Saat PG aktif, PostgreSQL = sumber kebenaran; file JSON = cermin. mtime file
di-netralkan (float("inf")) supaya file tidak menimpa state PG. Multi-proses
murni lewat file belum dijamin di mode PG (aplikasi ini satu proses server).

## Catatan sinkronisasi (jujur)
Commit 4c4c34a memuat kode + HASIL-72 + F-15/F-16/F-17, TETAPI skrip sinkron
STEPLOG/SESSION_STATE/ROADMAP mati di tengah (NameError: re tidak diimpor), sehingga
pesan commit sempat mengklaim 'sinkron' padahal belum. Disinkronkan di commit
lanjutan (docs-only) pada step yang sama.
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
