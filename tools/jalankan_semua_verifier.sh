#!/usr/bin/env bash
# Jalankan SEMUA tools/verify_*.py (verifikasi sungguhan). rc=1 bila ada yang merah.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p .out
# segarkan daftar cek lebih dulu supaya pengunci daftar tidak merah karena basi
python3 tools/hitung_verifier.py > .out/verifikasi-hitung.txt 2>&1 || true

total=0; merah=0; hijau=0
: > .out/verifikasi-ringkas.txt
for v in tools/verify_*.py; do
  nama="$(basename "$v")"
  python3 "$v" > ".out/verifikasi-$nama.txt" 2>&1
  rc=$?
  total=$((total + 1))
  if [ "$rc" = "0" ]; then hijau=$((hijau + 1)); printf '  ok    %s\n' "$nama"; else merah=$((merah + 1)); printf '  MERAH %s (rc=%s)\n' "$nama" "$rc"; fi
  printf '%s %s\n' "$rc" "$nama" >> .out/verifikasi-ringkas.txt
done
echo
echo "verifier: $total | hijau: $hijau | merah: $merah"
if [ "$merah" != "0" ]; then
  echo "yang merah:"
  awk '$1 != 0 {print "  - " $2}' .out/verifikasi-ringkas.txt
fi
[ "$merah" = "0" ] && exit 0 || exit 1
