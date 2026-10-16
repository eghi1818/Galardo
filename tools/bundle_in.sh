#!/bin/bash
# Gabung banyak file jadi SATU .md untuk di-upload ke chat.
# Pakai:
#   bash tools/bundle_in.sh OUT.md file1 file2 ...
#   bash tools/bundle_in.sh OUT.md --list daftar.txt
#   find . -name '*.py' | bash tools/bundle_in.sh OUT.md -
# Aman terhadap zsh (yang TIDAK memecah variabel tak dikutip).
OUT="$1"; shift
[ -z "$OUT" ] && { echo "pakai: bash tools/bundle_in.sh OUT.md file..."; exit 1; }
: > "$OUT"
N=0
add() {
  [ -z "$1" ] && return
  if [ -f "$1" ]; then
    printf '=== FILE: %s ===\n' "$1" >> "$OUT"
    cat "$1" >> "$OUT"
    printf '\n=== END FILE: %s ===\n\n' "$1" >> "$OUT"
    echo "  + $1"
    N=$((N + 1))
  else
    echo "  ! lewat (tidak ada): $1"
  fi
}
handle() {
  [ -z "$1" ] && return
  if [ -f "$1" ]; then add "$1"; return; fi
  for g in $1; do add "$g"; done
}
if [ "$1" = "--list" ]; then
  while IFS= read -r line; do handle "$line"; done < "$2"
elif [ "$1" = "-" ]; then
  while IFS= read -r line; do handle "$line"; done
elif [ "$#" -gt 0 ]; then
  for a in "$@"; do handle "$a"; done
fi
echo "selesai -> $OUT ($N file, $(wc -c < "$OUT" | tr -d ' ') byte)"
