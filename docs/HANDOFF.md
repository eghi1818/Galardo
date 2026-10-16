# HANDOFF — Galardo

Dokumen serah-terima. Kalau chat mati, mulai dari sini. Jangan baca riwayat chat.

## Titik aman
- Tag: `checkpoint/galardo-v1.1-mulai`
- Balik ke titik aman: `git reset --hard checkpoint/galardo-v1.1-mulai`

## Aturan kerja (WAJIB)
1. Satu langkah = satu patch = satu verifikasi = satu commit.
2. Patch selalu: cek anchor unik -> backup -> tulis -> `py_compile` -> uji.
3. Kalau uji merah: JANGAN commit, kirim output.
4. File yang belum dibaca: jangan disentuh.
5. Setiap commit hijau langsung di-push.
6. Chat Galardo (lama) DIBEKUKAN. Kerja hanya dari sini.
7. Chat hanya mengobrol. Kebenaran ada di Git.

## Peta status
Lihat `docs/ROADMAP.md` dan `docs/SESSION-HISTORY-COMPLETE.md`.
Titik terakhir: commit `c2d2932` (tangga kepemilikan, 27/0).

## Yang sudah selesai (ringkas)
- W1-W7: fondasi, ownership DNS TXT, down verdict, route override, plafon kapasitas
- Defect D5-D21 ditutup
- Tier 1 crypto: Ed25519 murni + node trust policy (39/0)
- Fase A patch 1: `backend/ownership_ladder.py` (27/0)
- Bukti: siklus DOWN penuh, ttr 43.938s, 3 situs nyata

## Langkah berikutnya
1. Fase A patch 2: sambungkan tangga ke `api.py`
2. Fase B: fleet, auto-knee, probe multi-jalur
3. Fase C: proxy lane (residential untuk PROBE, bukan beban), sambungkan `proxy.py`
4. Fase D: RBAC+MFA, backup, Docker Compose

## Belum diketahui (butuh upload)
UI (`templates/`, `static/`), `engine.py`, `transport.py`, `proxy.py`,
`capacity.py`, `routeoverride.py`, `observer.py`, `external_probe.py`,
`tests/tests_integration.py`, ekor backup chat.

## Keputusan yang sudah dikunci
- Residential proxy HANYA untuk jalur probe. Beban tetap direct/datacenter.
- Proxy mati != target DOWN. Butuh >=2 jalur probe independen.
- AI ditaruh di REA (perencana). Galardo tetap deterministik (hakim).
- Verdict "JENUH tapi tidak tumbang" sah dan harus diterima.
- Attestasi operator BUKAN bukti. Selalu berlabel + berbatas waktu.
