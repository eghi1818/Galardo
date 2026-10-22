# GALARDO — Setup T3 Cloudflare Edge Override

T3 membuat paksaan rute 404/blank **terlihat dari internet**, bukan hanya dari
localhost. Ini tier paling kuat untuk Goal 3, karena pengunjung nyata pun akan
menerima respons yang dipaksa.

Status: **terbukti live** 2026-10-15 dan diulang 2026-10-22 (STEP-118, `T3_OK`) di zone `koler.space`.

---

## 1. Token Cloudflare

Buat di https://dash.cloudflare.com/profile/api-tokens → Create Token →
Create Custom Token. Izin minimal:

| Scope | Resource | Level |
|---|---|---|
| Account | Workers Scripts | Edit |
| Zone | Workers Routes | Edit |
| Zone | DNS | Edit |
| Zone | Zone | Read |

Account Resources: Include → akun Anda.
Zone Resources: Include → Specific zone → zone Anda.

## 2. Variabel

Di `.env` (sudah masuk `.gitignore`):

    GALARDO_CF_TOKEN=<token>
    GALARDO_CF_ZONE_NAME=<zone>          # mis. koler.space
    GALARDO_CF_TEST_HOST=                # opsional; default galardo-edge.<zone>

`GALARDO_CF_ACCOUNT_ID` dan `GALARDO_CF_ZONE_ID` **tidak wajib** — ditemukan
otomatis dari token (butuh izin Zone:Read).

## 3. Jalankan

    make t3

Yang dilakukan, berurutan, dan setiap status HTTP dicatat:
1. `GET /user/tokens/verify` — validasi token
2. `GET /zones` — discovery zone + account
3. `GET /zones/<id>/dns_records?name=<host>` — cek record; buat A record
   `192.0.2.1` **proxied** kalau belum ada (route Worker hanya aktif untuk
   hostname yang proxied)
4. `PUT /accounts/<id>/workers/scripts/<name>` — upload Worker
   (coba format service-worker, fallback modules multipart)
5. `POST /zones/<id>/workers/routes` — bind pola `<host>/*`
6. probe HTTPS ke edge dengan cache-buster, retry maksimal 24 detik
7. revert: hapus route → worker → DNS record (kalau kita yang membuatnya)

## 4. Bukti yang diharapkan

    probe edge : {"status": 404, "header": "404", "attempts": 3}
    T3_OK

`attempts` > 1 itu normal: edge butuh beberapa detik menyebar.

## 5. Catatan jujur

- Route Worker **hanya** aktif untuk hostname yang proxied (orange cloud).
- `revert` menghapus DNS record kalau dibuat oleh Galardo. Pakai
  `GALARDO_CF_TEST_HOST` yang sudah ada kalau ingin record permanen.
- Path yang tidak cocok pola akan diteruskan ke origin. Kalau origin-nya
  `192.0.2.1` (TEST-NET, tidak ada apa pun), responsnya bisa 522/502 — itu
  wajar dan bukan kegagalan.
- Jangan pakai hostname yang sudah melayani situs produksi tanpa sadar:
  pola `<host>/*` akan mencegat path yang cocok di host itu.
