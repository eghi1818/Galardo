#!/usr/bin/env bash
# GALARDO fleet helper — register workers / check fleet status
# Usage:
#   GALARDO_API=http://host:8090 ./deploy_fleet.sh register w-jkt-1 w-sgp-1 ...
#   GALARDO_API=http://host:8090 ./deploy_fleet.sh status
set -euo pipefail
API="${GALARDO_API:-http://127.0.0.1:8090}/api/v1"

cmd="${1:-status}"; shift || true

case "$cmd" in
  register)
    for w in "$@"; do
      region=$(echo "$w" | cut -d- -f2)
      curl -s -X POST "$API/workers" -H "Content-Type: application/json" -d "{
        \"id\":\"$w\",\"name\":\"$w\",\"expertise\":\"distributed-k6-$region\",
        \"capabilities\":[\"GET\",\"POST-safe\",\"ramp\",\"burst\",\"weighted-mix\",\"long-duration\",\"high-concurrency\",\"k6\"],
        \"kind\":\"k6-remote\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print('registered:',d.get('id'),d.get('status'))"
    done
    ;;
  status)
    curl -s "$API/workers" | python3 -c "
import sys,json
ws=json.load(sys.stdin)
print(f'{len(ws)} workers:')
for w in ws:
    print(f\"  {w['id']:14} {w.get('expertise',''):24} {w.get('status',''):8} job={w.get('current_job_id')}\")"
    ;;
  *)
    echo "usage: deploy_fleet.sh [register w1 w2 ... | status]"; exit 2 ;;
esac
