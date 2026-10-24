# GALARDO - Ketahanan Sesi (Session Resilience)

> **BACA WAJIB (setiap chat, tanpa kecuali): `docs/GOAL-GALARDO.md`.**
> Tujuan Galardo = membuat target MATI / tidak bisa diakses (Layer 7; target payment
> gateway seperti DOKU -> Akamai Reference #102 / halaman fallback / circuit breaker).
> Wajib: multi-IP (pool/rotasi), request sah secara sintaksis, asimetri di endpoint berat,
> targeting dari intel REA, dan memutus rantai edge->origin. Kalau benturan soal TUJUAN,
> GOAL-GALARDO.md yang menang. Anti-pola terlarang ada di sana.

## 1. Pemicu
Sesi bisa mati mendadak ("Response failed" / "An unexpected error occurred").
Sebab utama: balasan agen terlalu panjang + konteks percakapan menumpuk.
Retry biasanya gagal lagi. Obatnya struktural, bukan mengulang.

## 2. Sumber kebenaran
- Status sesi : docs/SESSION_STATE.md (kecil, diperbarui tiap STEP)
- Rencana     : docs/HANDOFF.md bagian 8
- Larangan    : docs/EMERGENCY.md
- Riwayat    : docs/STEPLOG.md (satu baris per STEP)
Kalau dokumen bertentangan dengan kode, KODE yang benar. Laporkan, jangan ikuti dokumen buta.

## 3. Protokol sesi baru (wajib, urut)
1. Baca lampiran saja: docs/ONBOARDING_PROMPT.txt + docs/SESSION_STATE.md. Jangan baca riwayat chat lama.
2. Baca output bash tools/resume.sh yang di-paste user.
3. Cross-check SESSION_STATE vs kode dan git; tandai status dokumen yang basi.
4. Lapor ringkas: HEAD, branch, ahead/behind, dirty, hasil tes, item aktif, item berikutnya.
5. Tunggu konfirmasi "lanjut" sebelum menyentuh kode.

## 4. Anggaran balasan (anti Response failed)
- Maksimum ~250 baris kode/blok per balasan. Lebih dari itu: pecah STEP-xxA / xxB / xxC.
- Satu balasan = satu blok bash siap tempel (kecuali pecahan sub-step).
- Jangan tempel ulang isi file yang sudah ada di repo; rujuk path + baris.
- Jangan ulangi penjelasan yang sudah ada di dokumen.

## 5. Anggaran laporan terminal
- Perintah memangkas outputnya sendiri: tail -n, grep -E, atau tulis ke .out lalu tempel ringkasannya.
- Setiap perintah diikuti: echo "exit=$?"
- Tempel hanya bagian yang berubah atau gagal, bukan seluruh log.

## 6. Kalau STEP mati di tengah
1. git status --porcelain ; git stash list ; ls -1t .out | head
2. File setengah jadi (sisa heredoc): tuntaskan atau hapus. Jangan commit setengah.
3. Catat kondisi di docs/SESSION_STATE.md, lalu buka sesi baru.

## 7. Titik pulih
- Sebelum patch besar: git tag checkpoint/<step>-mulai
- Commit kecil per STEP, jangan menumpuk.

## 8. Yang dilampirkan saat sesi baru
Hanya: docs/ONBOARDING_PROMPT.txt + docs/SESSION_STATE.md + output tools/resume.sh.
HASIL-xx.md hanya dilampirkan kalau STEP terakhir GAGAL.

## 9. Konvensi bukti (HASIL-xx)
- SATU tempat saja: docs/HASIL-xx.md. Tidak ada mirror ke .out/.
- Alasan: .out/ di-ignore git - file di sana tidak ikut ter-commit dan bisa hilang.
- docs/ sudah jadi rumah dokumen sejenis (T3-RUN.md, E2E-RUN.md, CF-EDGE-SETUP.md).
- .out/ dipakai untuk: log mentah terminal, backup, file sementara.
- Nama file: docs/HASIL-<nomor STEP>.md

## 10. Gate wajib sebelum commit
- Setiap commit harus lulus: make test (0 failed), smoke, verifier terkait, dan node --check bila ada JS.
- Exit code != 0 pada salah satu -> JANGAN commit.
- Verifikasi dilakukan SEBELUM commit, bukan sesudah.

## 11. Checklist pra-commit (wajib)
- make test hijau, 0 failed, dan jumlahnya TIDAK TURUN
- verifier terkait + smoke hijau
- SESSION_STATE.md diperbarui: Tes (angka nyata), STEP terakhir, Item berikutnya, Eksekusi
- STEPLOG.md bertambah satu baris + acuan tes disamakan
- tidak ada temuan yang sudah ditutup masih dicantumkan sebagai terbuka

> STATUS SEKARANG (kondisi terkini + blocker): `docs/STATUS-SEKARANG.md`
