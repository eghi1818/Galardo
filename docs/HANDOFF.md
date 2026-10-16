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
- STEP terakhir selesai: STEP-13 (cache buster, 36/36 hijau), commit d73878a
- Sedang dikerjakan: STEP-14 (handoff + wiring cache buster ke engine/step_load)
- Tes acuan: make test 59/59, trust 39/39, ownership_ladder 27/27, ladder API 18/18, cachebuster 36/36

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

## 8. PENDING BERIKUTNYA
1. STEP-15: auto-knee sebelum spike (ukur plafon dulu)
2. Probe multi-jalur + kesiapan residential (field proxy_pool)
3. Atribusi lapisan verdict: DNS / edge / origin / app
4. Satukan GALARDO_LOCAL_DEV ke tangga kepemilikan
5. Tier 1 sisa: RBAC+MFA, backup otomatis, Docker Compose
6. Tier 2-4: Postgres, NATS, OTel, alerting
7. Run end-to-end nyata pasca perubahan Tier 1 + Fase A
