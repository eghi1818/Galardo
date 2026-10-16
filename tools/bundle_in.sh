#!/bin/bash
# Gabung banyak file jadi SATU .md untuk di-upload ke chat.
# Pakai: bash tools/bundle_in.sh KELUARAN.md file1 file2 ...
OUT="$1"; shift
[ -z "$OUT" ] && { echo "pakai: bash tools/bundle_in.sh KELUARAN.md file..."; exit 1; }
: > "$OUT"
for f in "$@"; do
  if [ -f "$f" ]; then
    printf '=== FILE: %s ===\n' "$f" >> "$OUT"
    cat "$f" >> "$OUT"
    printf '\n=== END FILE: %s ===\n\n' "$f" >> "$OUT"
    echo "  + $f"
  else
    echo "  ! lewat (tidak ada): $f"
  fi
done
echo "selesai -> $OUT ($(wc -c < "$OUT") byte)"
