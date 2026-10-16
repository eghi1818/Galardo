#!/usr/bin/env bash
# GALARDO - resume ringkas untuk sesi chat baru. Output sengaja dipangkas.
cd "$(dirname "$0")/.." || exit 1
echo "== GALARDO RESUME $(date -u +%Y-%m-%dT%H:%M:%SZ) =="
echo "HEAD   : $(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"
echo "BRANCH : $(git branch --show-current)"
set -- $(git rev-list --left-right --count origin/main...HEAD 2>/dev/null)
echo "TRACK  : behind=$1 ahead=$2"
echo "DIRTY  : $(git status --porcelain | wc -l | tr -d ' ') file"
git status --porcelain | head -n 8
echo "-- 3 step terakhir --"
grep -E '^\| [0-9]+' docs/STEPLOG.md | tail -n 3
echo "-- pending HANDOFF bagian 8 --"
sed -n '/^#\{1,4\}[[:space:]]*8[.)[:space:]]/,/^#\{1,4\}[[:space:]]*9[.)[:space:]]/p' docs/HANDOFF.md \
  | grep -E '^[[:space:]]+[0-9]+\.' | head -n 12
echo "-- .out terbaru --"
ls -1t .out 2>/dev/null | head -n 3
echo "-- guard --"
bash tools/step_guard.sh >/dev/null 2>&1 && echo "step_guard OK" || echo "step_guard GAGAL"
