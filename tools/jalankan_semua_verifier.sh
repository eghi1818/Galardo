#!/usr/bin/env bash
# Jalankan SEMUA tools/verify_*.py SEKALI + progres. rc=1 bila ada yang merah.
set -u
trap '' HUP   # jangan mati kalau tab/jendela ditutup
cd "$(dirname "$0")/.." || exit 1
mkdir -p .out
T0=$(date +%s)
echo "== verifikasi: SEMUA tools/verify_*.py (sekali jalan) =="
python3 tools/hitung_verifier.py --daftar >/dev/null 2>&1 || true
total=0; merah=0; hijau=0
: > .out/verifikasi-ringkas.txt
for v in tools/verify_*.py; do
  nama="$(basename "$v")"; s=$(date +%s)
  python3 "$v" > ".out/verifikasi-$nama.txt" 2>&1; rc=$?
  d=$(( $(date +%s) - s )); total=$((total + 1))
  if [ "$rc" = "0" ]; then hijau=$((hijau + 1)); printf '  ok    %-40s %3ss  %s\n' "$nama" "$d" "$(date '+%H:%M:%S')"
  else merah=$((merah + 1)); printf '  MERAH %-40s %3ss  %s\n' "$nama" "$d" "$(date '+%H:%M:%S')"; fi
  printf '%s %s\n' "$rc" "$nama" >> .out/verifikasi-ringkas.txt
done
python3 tools/hitung_verifier.py --dari-out >/dev/null 2>&1 || true
echo
echo "verifier: $total | hijau: $hijau | merah: $merah | durasi $(( $(date +%s) - T0 ))s"
if [ "$merah" != "0" ]; then echo "yang merah:"; awk '$1 != 0 {print "  - " $2}' .out/verifikasi-ringkas.txt; exit 1; fi
exit 0
