#!/bin/bash
# Audit disiplin git: tree bersih, sinkron dengan origin, tidak ada yang tertinggal.
REPO="/Users/eghi/Documents/REPO/Galardo/Galardo-main"
cd "$REPO" || { echo "REPO TIDAK ADA"; exit 1; }
fail=0
b="$(git rev-parse --abbrev-ref HEAD)"
echo "== AUDIT DISIPLIN GIT =="
echo "  repo   : $REPO"
echo "  branch : $b"
if [ -n "$(git status --porcelain)" ]; then
  echo "  [X] working tree KOTOR - ada yang belum di-commit:"
  git status --short | head -20
  fail=1
else
  echo "  [v] working tree bersih"
fi
git fetch origin --quiet 2>/dev/null
ahead="$(git rev-list --count "origin/$b..$b" 2>/dev/null || echo '?')"
behind="$(git rev-list --count "$b..origin/$b" 2>/dev/null || echo '?')"
echo "  ahead  : $ahead   behind: $behind"
if [ "$ahead" != "0" ]; then
  echo "  [X] ADA $ahead COMMIT BELUM DI-PUSH:"
  git log --oneline "origin/$b..$b"
  fail=1
fi
if [ "$behind" != "0" ]; then echo "  [!] ketinggalan $behind commit dari origin - jalankan git pull"; fi
sn="$(git stash list | wc -l | tr -d ' ')"
if [ "$sn" != "0" ]; then echo "  [!] ada $sn stash nyangkut"; fi
echo
if [ "$fail" = "0" ]; then echo "== AMAN: lokal == origin, tidak ada yang tertinggal ==";
else echo "== ADA YANG TERTINGGAL - beresi dulu =="; fi
exit $fail
