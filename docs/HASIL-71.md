# HASIL-71 — Klien PostgreSQL wire v3 minimal (stdlib)

Status: SELESAI — uji live HIJAU.
Catatan koreksi: klaim "berhasil" di versi awal file ini SALAH (uji live saat itu
gagal di paket startup). Koreksi dilakukan di STEP yang sama, bukan diakui belakangan.

## Yang dibangun
backend/pg.py — klien protokol wire PostgreSQL v3, murni stdlib (tanpa psycopg):
- paket startup v3 + terminator NUL
- auth scram-sha-256 (PBKDF2/HMAC, channel binding "n,,") dan md5
- verifikasi tanda tangan server (AuthenticationSASLFinal, R/code 12)
- fail-open: GALARDO_PG_DSN kosong -> pemanggil pakai JSON lokal

## Bukti uji live (container pg, PostgreSQL 16.15)
    connect OK
    version: PostgreSQL 16.15 on aarch64-unknown-linux-musl, compiled by gcc (Alpine 15.2.0)
    LIVE_OK
    DBG expect_sig == DBG recv_v   (tanda tangan server cocok, diverifikasi server)
    docker compose logs pg | grep FATAL  -> kosong

## Gate
    python3 tools/verify_pg.py -> RESULTS: 35 passed, 0 failed
    python3 -m py_compile backend/pg.py -> OK
    make test -> lihat STEPLOG (acuan gate di blok berikutnya)

## Temuan yang lahir DAN ditutup di step ini
F-13 (P1) startup packet tanpa terminator NUL -> server menolak
     'invalid startup packet layout: expected terminator as last byte'
     fix: b"\x00" di akhir body startup; verifier menambah cek terminator ganda.
F-14 (P1) SCRAM rusak — 5 sub-defect, semuanya di jalur auth:
     1. SASLResponse ('p' saat SCRAM) dikirim dengan NUL -> PG menolak dengan
        'malformed SCRAM message / Message length does not match input length'
     2. nonce klien ditulis DUA kali di client-final (nonce + parts["r"]),
        padahal parts["r"] server sudah memuat nonce klien penuh
     3. AuthMessage klien salah bentuk: gs2 header 'n,,' ikut ter-HMAC dan
        server-first (r=,s=,i=) hilang dari HMAC
     4. pesan R/code 12 (AuthenticationSASLFinal) belum ditangani sama sekali
     5. tanda tangan server dihitung di atas AuthMessage TERPOTONG (2 bagian,
        bukan 3) -> selalu 'tanda tangan server SCRAM tidak cocok'
     fix: tanpa NUL untuk SASL, r= pakai snonce saja, AuthMessage = bare+server-first,
     tangani code 12 dengan verifikasi, helper scram_server_signature(+snonce)
     supaya simetris dengan scram_client_final.

## Kunci anti-regresi
tools/verify_pg.py memuat VEKTOR RFC 7677 (SCRAM-SHA-256, password "pencil"):
client-final dan ServerSignature harus persis sama dengan contoh RFC. Bug nonce-dobel
dan AuthMessage-terpotong tidak bisa kembali tanpa membuat vektor ini gagal.

## Pelajaran
Hijau offline BUKAN berarti protokol benar. verify_pg sempat 30/30 hijau sementara
uji live gagal dua kali berturut-turut (F-13, lalu F-14). Uji live harus jadi bagian
gate untuk modul protokol, bukan opsional.
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
