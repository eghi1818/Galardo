# HANDOFF — GALARDO
> Baca file ini DULU. Jangan baca riwayat chat. Chat itu pengobrolan; kebenaran ada di Git.

## 0. REPO KANONIK (TERKUNCI)
    /Users/eghi/Documents/REPO/Galardo/Galardo-main
    remote: git@github.com:eghi1818/Galardo.git
WAJIB: setiap perintah diawali `cd /Users/eghi/Documents/REPO/Galardo/Galardo-main` + cek `pwd -P`.
Peta lengkap + aturan mutlak: docs/CONTEXT.md. Prosedur darurat: docs/EMERGENCY.md.

## 1. TITIK AMAN
    git reset --hard checkpoint/galardo-v1.1-mulai
Tag sudah di-push. Cek: `git tag -l 'checkpoint/*'`

## 2. PROTOKOL LANJUT (WAJIB DIPATUHI)
1. Satu langkah = satu patch = satu verifikasi = satu commit. Tidak digabung.
2. Patch selalu: cek anchor unik -> backup -> tulis -> py_compile -> uji.
3. Uji MERAH = jangan commit. Kirim output, tunggu instruksi.
4. File yang belum pernah dibaca = jangan disentuh.
5. Setiap STEP ditulis ke docs/steps/STEP-xx.md, output ke .out/.
6. STEP baru dihitung SELESAI setelah tools/git_discipline.sh lolos.
7. Push gagal = STOP, lapor.

## 3. STATUS (lihat juga docs/STEPLOG.md)
- STEP terakhir selesai: STEP-15 (fix import step_load + smoke test), commit 31d95d0
- SELESAI juga: STEP-14 (handoff darurat + wiring cache buster ke engine/scenario/step_load)
- Sedang dikerjakan: STEP-16 (first-prompt ke repo + selaraskan dokumen)
- Tes acuan: make test 61/61, smoke OK, trust 39/39, ownership_ladder 27/27,
  ladder API 18/18, cachebuster 36/36
- Bukti hidup cache buster: 100/100 request membawa ?__gb=<nonce>; mode OFF = 0

## 4. PETA MODUL (backend/)
- Inti: engine.py, step_load.py, transport.py, netdns.py, assertions.py, safety.py, scenario.py
- Kepemilikan: ownership.py (TXT DNS), ownership_ladder.py (tangga 4 rung)
- Jalur: routeoverride.py, origindiscovery.py, cloudflare.py
- Observasi: observer.py, external_probe.py, capacity.py (tools/)
- Kripto/tier1: ed25519.py, envelope.py, trust.py
- Goal 2: cachebuster.py (nonce ?__gb + deteksi cache HIT)
- Baru: bundle_in.sh / bundle_out.sh / git_discipline.sh / step_guard.sh (tools/)

## 5. ATURAN MUTLAK
1. Mode Aktif terverifikasi, bukan dashboard pasif.
2. Goal 2 WAJIB pakai cache-buster ?__gb=<nonce> agar menembus CDN ke origin.
3. Goal 3 hanya lewat Tier sah: T1 hosts, T2 shim lokal, T3 Cloudflare Edge Rule.
4. Fail-closed: GATE 0 kepemilikan, GATE 1 canary, GATE 2 toleransi fase 70/30.
5. Attestasi operator BUKAN bukti. Selalu berlabel + berbatas waktu.
6. Proxy pihak ketiga HANYA untuk jalur probe, bukan beban utama.
7. Proxy mati != target DOWN. Butuh >=2 jalur probe independen.
8. Verdict "JENUH tapi tidak tumbang" sah dan harus diterima.
9. AI ditaruh di REA (perencana). Galardo tetap deterministik (hakim).

## 6. JEBAKAN SHELL (zsh)
- `path` terikat ke PATH. `while read -r path` MENGHANCURKAN PATH -> pakai `rel`/`f`/`line`.
- zsh TIDAK memecah variabel tak dikutip: `cmd $LIST` = satu argumen -> pakai `--list`.

## 7. BELUM DIKETAHUI (butuh upload)
UI (dashboard/, templates/), proxy.py (TIDAK ADA - transport.py sudah punya proxy),
ekor backup chat, dokumen REA lanjutan, isi 14 poin list kendala per-item.

## 8. PENDING BERIKUTNYA (URUT PRIORITAS - jangan dilompati)

STATUS STEP-102: item 1-10 di bawah SEMUA SELESAI. Backlog resmi + status + bukti ada di
docs/PENDING.md (bagian "Status per ..."). SISA: usul P7 (botnet) dan Tier 3-4 (NATS, OTel,
alerting). Jangan buka lebih dari satu item sekaligus (lihat 8b).

RIWAYAT (jangan dikerjakan ulang):

P0 - Goal 2 inti (paling menentukan)
  1. [SELESAI STEP-26] Migrasi SEMUA modul HTTPS ke backend/netssl.context():
     engine.py, observer.py, routeoverride.py, safety.py, srccap.py,
     step_load.py, transport.py   (external_probe.py sudah)
  2. [SELESAI STEP-32..39] Sambungkan auto-knee ke preflight: ukur plafon (tools/galardo_capacity.py)
     SEBELUM spike, jangan tembak buta.

P1 - Universalitas
  3. [SELESAI STEP-54] Jalur probe residential (field proxy_pool masih ditolak sebagai field asing)
  4. [SELESAI STEP-55] Verifikasi rung dns_txt (rank 4) kepemilikan end-to-end di koler.space
  5. [SELESAI STEP-48] T3 end-to-end di koler.space: Worker + route, buktikan 404/blank

P2 - Produk (yang dipakai manusia)
  6. [SELESAI STEP-56] AUDIT DASHBOARD: peta di docs/UI-API-GAP.md + docs/DASHBOARD-AUDIT.md
  7. [SELESAI STEP-58..63] Alur UI:
     - 6 irisan selesai: Ownership(58), Sources(59), Bukti&observer(60), Overrides(61), probe-contract(62), Webhooks+remote-dispatch(63). target -> intel REA -> preflight -> playbook -> jalankan -> verdict

P3 - Kesiapan produksi
  8. [SELESAI STEP-64..67] Tier 1: RBAC(64) + MFA(65) + backup(66) + Docker Compose(67)
  9. [SEBAGIAN SELESAI STEP-72] Tier 2-3: Postgres; sisa NATS, OTel, alerting
 10. Run end-to-end nyata pasca semua perubahan  [SELESAI STEP-73 - docs/HASIL-73.md]

## 8b. ATURAN PRIORITAS
- Temuan sampingan DICATAT di sini; jangan langsung dikerjakan kecuali
  menghalangi item P0.
- Satu item P0 selesai -> baru naik ke P1.
- Jangan buka lebih dari satu item sekaligus.
- P0.1b: TUTUP (STEP-74) - ownership_ladder.default_fetcher() sudah lewat netssl.context().
- F-2 DITUTUP (STEP-57): /healthz & /admin/secret adalah path sisi-target, bukan route API; API sudah punya GET /health. F-3 CSP TUTUP (STEP-76, diperketat nonce di STEP-98); F-4 CORS TUTUP (STEP-76).

## 8c. INVENTARIS LENGKAP
Status per item (V/D/goals/dokumen/tier) ada di docs/INVENTARIS.md.
CEK DULU sebelum mengerjakan apa pun, supaya tidak overlap.

## 9. DONE RINGKAS (jangan dikerjakan ulang)
STEP 01-101 selesai (termasuk F-1..F-24, P0.1b, P1-P6). Rincian: docs/STEPLOG.md.
Langkah terakhir: STEP-102 (dokumen handoff ini).
