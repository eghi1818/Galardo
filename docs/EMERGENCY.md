# PROTOKOL DARURAT — kalau chat hang / error

## Yang TIDAK hilang
- Semua kode, tes, tag, dan riwayat ada di Git dan sudah di-push.
- Hook post-commit auto-push: setiap commit langsung ke GitHub.

## 60 detik pertama (chat baru)
1. Jangan jelaskan panjang. Upload/tekan isi docs/HANDOFF.md + docs/EMERGENCY.md.
2. Tempel blok dari `bash tools/onboard.sh`.
3. Minta agent baru: "baca HANDOFF, lalu jalankan tools/step_guard.sh dan tools/git_discipline.sh,
   laporkan status, jangan sentuh kode dulu."

## Perintah pemulihan
    cd /Users/eghi/Documents/REPO/Galardo/Galardo-main
    bash tools/step_guard.sh
    bash tools/git_discipline.sh
    git log --oneline -10
    make test            # acuan: 79 passed, 0 failed
    git reset --hard checkpoint/galardo-v1.1-mulai   # kalau perlu mundur

## Kalau push gagal
    git push origin main        # ulangi manual; hook tidak menggantikan ini
    git status -sb              # pastikan tidak ada "ahead"

## Aturan agent baru
- Jangan menebak isi file yang belum dibaca.
- Jangan mengerjakan lebih dari satu STEP sebelum melapor.
- Ikuti docs/CONTEXT.md; jangan baca riwayat chat lama.
