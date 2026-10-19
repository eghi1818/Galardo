# HASIL-98 — P6 TUTUP: nonce CSP per-respons

STEP: 98 — Item: P6 (docs/PENDING.md), prioritas P3.

## Yang diubah
- backend/api.py: helper `_csp_harden()` (nonce wajib di script-src/style-src,
  'unsafe-inline' hanya di script-src-attr/style-src-attr); jalur env
  `GALARDO_CSP` tanpa placeholder `{nonce}` tidak lagi dikembalikan mentah (dulu
  -> CSP tanpa nonce, script inline diblokir); substitusi `{{NONCE}}` di level
  byte, tanpa decode/encode utf-8 `errors="replace"`; nama lokal `CSP` -> `csp`.
  Tidak perlu hoist: `send_header` CSP memang sudah di dalam cabang `.html`.
- dashboard/index.html: atribut `nonce="{{NONCE}}"` pada `<style>` dan `<script>`.
- tools/verify_dashboard_pages.py: regex `<script>` dulu tidak toleran atribut,
  sehingga `node --check` atas script dashboard diam-diam tidak berjalan sejak
  nonce dipasang. Kini regex toleran + `group(2)`, plus cek nonce/style/placeholder
  dan cek `_csp()` runtime di 3 varian env.
- tools/verify_headers.py: cek "CSP terpasang pada HTML" mengunci literal
  `..., CSP)` sehingga patah oleh rename lokal. Kini toleran nama variabel, plus
  cek baru yang mengikat jalur HTML ke `_csp`/nonce.

## Keputusan
- Versi ketat dipertahankan: `'unsafe-inline'` TIDAK dikembalikan ke `script-src`.
- Batas browser: `script-src-attr`/`style-src-attr` dikenali Safari >= 15.4,
  Chrome >= 75, Firefox >= 75. Di browser lebih lama 53 handler `on*` mati
  (navigasi href tetap jalan). Kalau perlu, tambah `'unsafe-inline'` ke
  `script-src` = 1 baris.

## Catatan dokumen (belum dikerjakan)
- STEPLOG.md: baris 81-96 tidak ada (lompat 80 -> 97); docs/HASIL-8*/9* hanya
  ada 80, 85, 87, 88, 97.
- docs/SESSION_STATE.md menyebut bukti "bukan .out/", padahal docs/CONTEXT.md
  menetapkan output STEP ke .out/. Dua-duanya dipakai: .out mentah, docs rekaman.
- docs/EMERGENCY.md masih menulis acuan `make test` 61 passed (kini 79).
- Global `CSP` (api.py baris 43) kini tidak dipakai siapa pun; `_csp()` punya
  template inline sendiri -> risiko drift. Kandidat langkah kecil terpisah.
- 12 traceback `ConnectionResetError` di keluaran gate = noise keep-alive.

## Bukti
```
311:== GATE selesai (rc=0) ==
```
