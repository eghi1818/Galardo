#!/usr/bin/env bash
# Galardo - KIT RESUME minimal. Root kit HANYA berisi yang perlu dilampirkan/tempel.
# Sisanya masuk arsip/. Idempoten: folder kit dibangun ulang dari nol.
set -u
REPO="${GALARDO_REPO:-$HOME/Documents/REPO/Galardo/Galardo-main}"
KIT="${GALARDO_KIT:-$HOME/Desktop/GALARDO-RESUME}"

[ -d "$REPO" ] || { echo "repo TIDAK ADA: $REPO"; exit 1; }
cd "$REPO" || exit 1
rm -rf "$KIT"
mkdir -p "$KIT/arsip"

HEAD_SHA="$(git log --oneline -1)"
TGL="$(date '+%Y-%m-%d %H:%M')"

# --- 4 file yang HARUS dilampirkan ke chat baru ---
cp docs/GOAL-GALARDO.md  "$KIT/01-GOAL-GALARDO.md"
cp docs/STATUS-SEKARANG.md "$KIT/02-STATUS-SEKARANG.md"
cp docs/V1.4.md          "$KIT/03-V1.4.md"
cp docs/TARGET-BUKTI.md  "$KIT/04-TARGET-BUKTI.md"

# --- file untuk DITEMPEL (bukan dilampirkan) ---
cat > "$KIT/TEMPEL-KE-CHAT-BARU.txt" <<PEOF
Halo. Ini lanjutan proyek GALARDO (bukan dari nol). Repo: $REPO (HEAD: $HEAD_SHA).

LAMPIRAN yang saya berikan: 01-GOAL-GALARDO.md, 02-STATUS-SEKARANG.md, 03-V1.4.md, 04-TARGET-BUKTI.md.
Baca keempatnya DULU. GOAL-GALARDO.md bersifat MENGIKAT.

TUGAS PERTAMA (jangan menebak):
1. Jalankan di repo: \`make gate\` lalu \`make test\`. Laporkan angka rc APA ADANYA.
2. Sebutkan versi (V1.4) + HEAD yang Anda lihat sebelum mengusulkan apa pun.

ATURAN KERJA (jangan diubah):
- Bukti mentah dulu sebelum menambal; jangan menebak akar masalah.
- Cek struktur kode via AST/behavioral, bukan cari teks literal.
- Patch idempoten + verifikasi; commit + push tiap langkah HIJAU.
- Klaim "selesai/terbukti" hanya sah kalau verifier hijau; tulis rc apa adanya.
- Blok terminal wajib zsh-safe (awali \`setopt no_bang_hist\` + \`unsetopt nomatch\`).

GOAL: target MATI / tidak bisa diakses lewat Layer 7 (Error #102 / 502 / 504), request 100% sah di mata WAF,
dari banyak IP. KPI = target mati, bukan throughput. Galardo tidak boleh kalah dari Galado.

SISA: (a) kredensial anyip.io -> verify_egress_rotation (IP unik >= 2); (b) pindah VPS + verifikasi di VPS;
(c) bukti BEBAN pada wecash.ai + waspadaweb.com (verdict + 3 saksi + falsifikasi + bukti ber-hash).
PEOF

cat > "$KIT/00-BACA-DULU.txt" <<KITEOF
GALARDO RESUME KIT - dibuat $TGL - repo $REPO - HEAD $HEAD_SHA

LANGKAH (kalau chat lama mati/hang/error):
1. Terminal:  cd ~/Desktop/GALARDO-RESUME && bash resume.sh
2. Buka chat agent BARU.
3. LAMPIRKAN 4 file ini saja:
     01-GOAL-GALARDO.md
     02-STATUS-SEKARANG.md
     03-V1.4.md
     04-TARGET-BUKTI.md
4. TEMPEL isi: TEMPEL-KE-CHAT-BARU.txt
5. Folder arsip/ = salinan lengkap (tidak perlu dilampirkan).

Kalau agent baru menebak-nebak: suruh baca 01-GOAL-GALARDO.md dan jalankan \`make gate\`.
Verifikasi integritas kit: shasum -a 256 -c SHA256SUMS
KITEOF

cat > "$KIT/resume.sh" <<'REOF'
#!/usr/bin/env bash
# GALARDO-RESUME: cek kesehatan repo + integritas kit. Aman diulang.
set -u
REPO="${GALARDO_REPO:-$HOME/Documents/REPO/Galardo/Galardo-main}"
KIT="$(cd "$(dirname "$0")" && pwd)"
echo "== GALARDO RESUME =="
[ -d "$REPO" ] || { echo "repo TIDAK ADA: $REPO"; exit 1; }
cd "$REPO" || exit 1
echo "HEAD    : $(git log --oneline -1)"
echo "versi   : $(head -1 docs/V1.4.md 2>/dev/null | sed 's/^# *//')"
echo "kotor   : $(git status --porcelain | wc -l | tr -d ' ') file"
echo "verifier: $(ls -1 tools/verify_*.py 2>/dev/null | wc -l | tr -d ' ') file"
echo
echo "-- integritas kit --"
( cd "$KIT" && shasum -a 256 -c SHA256SUMS 2>/dev/null | grep -c "OK" | sed 's/^/  file OK: /' )
echo
echo "-- langkah berikut --"
echo "  1) make gate   (SEMUA verifier, rc harus 0)"
echo "  2) make test   (suite integrasi, rc harus 0)"
echo "  3) lampirkan 4 file LAMPIRAN + tempel TEMPEL-KE-CHAT-BARU.txt"
REOF
chmod +x "$KIT/resume.sh"

# --- arsip: sisanya (tidak perlu dilampirkan) ---
for f in docs/ONBOARDING_PROMPT.md docs/ONBOARDING_PROMPT.txt docs/SESSION_STATE.md docs/CONTEXT.md \
         docs/HANDOFF.md docs/RESILIENCE.md docs/INVENTARIS.md docs/PENDING.md docs/STEPLOG.md \
         docs/DEPLOY-VPS.md docs/KREDENSIAL-ANYIP.md docs/BUKTI-404.md docs/CF-EDGE-SETUP.md docs/T3-RUN.md; do
  [ -f "$f" ] && cp "$f" "$KIT/arsip/$(basename "$f")"
done
mkdir -p "$KIT/arsip/docs"
cp docs/*.md "$KIT/arsip/docs/" 2>/dev/null || true

( cd "$KIT" && find . -type f ! -name SHA256SUMS -print0 | xargs -0 shasum -a 256 > SHA256SUMS )

echo "KIT (root):"; ls -1 "$KIT" | sed 's/^/  - /'
echo "arsip: $(ls -1 "$KIT/arsip" | wc -l | tr -d ' ') item"
