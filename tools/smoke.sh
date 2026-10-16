#!/bin/bash
# Smoke test cepat: modul yang TIDAK dijalankan make test tapi bisa crash.
REPO="/Users/eghi/Documents/REPO/Galardo/Galardo-main"
cd "$REPO" || exit 1
rc=0
echo "== SMOKE: import + startup =="
for f in backend/step_load.py backend/cachebuster.py backend/ownership_ladder.py; do
  if python3 -c "import sys,os; sys.path.insert(0,'backend'); import $(basename "$f" .py)" 2>/tmp/smoke.err; then
    echo "  [v] import ok: $f"
  else
    echo "  [X] IMPORT GAGAL: $f"; cat /tmp/smoke.err; rc=1
  fi
done
echo "== SMOKE: step_load benar-benar jalan =="
python3 -m http.server 18101 --directory /tmp >/dev/null 2>&1 &
P=$!
sleep 1
if python3 backend/step_load.py http://127.0.0.1:18101/ 5 2 >/tmp/smoke2.log 2>&1; then
  echo "  [v] step_load jalan"
else
  echo "  [X] step_load CRASH"; tail -5 /tmp/smoke2.log; rc=1
fi
kill $P 2>/dev/null
if [ "$rc" = "0" ]; then echo "== SMOKE OK =="; else echo "== SMOKE GAGAL =="; fi
exit $rc
