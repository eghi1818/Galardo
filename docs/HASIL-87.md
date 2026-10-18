# HASIL-87 — P3: subfinder & nikto tersedia di image Docker

Status: SELESAI.

## Yang diubah
Dockerfile: layer apt (ca-certificates, curl, perl, unzip) + nikto 2.5.0 (perl, symlink
/usr/local/bin/nikto) + subfinder 2.6.7 (biner Go, arsitektur mengikuti image via
`dpkg --print-architecture`). Image sebelumnya hanya python polos + PyYAML.

## Bukti
    docker compose build rc=0 ; container running/healthy
    exec: subfinder -version ; nikto -Version ; command -v keduanya
    GET /api/v1/exttools -> subfinder & nikto available=true
    make gate rc=0 ; make test 79/0

## Catatan
Jalur fail-open tetap berlaku: kalau unduhan gagal saat build, image tetap dibangun
(dengan tool absen) - hanya panel Tools yang menampilkan "TIDAK ADA".
