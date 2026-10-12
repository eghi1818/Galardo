#!/usr/bin/env bash
# GALARDO — Fleet Parallel Launcher (Server B / load generator)
# Menjalankan N worker daemon paralel dalam satu VM, masing-masing proses
# independen dengan identitas unik (w11-jkt-1, w12-jkt-1, ...).
#
# Usage:
#   ./fleet-launch.sh start <api_base> <jumlah_worker> [prefix]
#   ./fleet-launch.sh stop [prefix]
#   ./fleet-launch.sh status <api_base>
#
# Contoh (Server B, 4 worker paralel):
#   GALARDO_ID_POOL_FILE=/data/id_pool.json ./fleet-launch.sh start http://ORCH:8090 4 w

set -euo pipefail

API="${2:-}"
N="${3:-4}"
PREFIX="${4:-w}"
WORKER_DIR="$(cd "$(dirname "$0")/../backend" && pwd)"
PID_DIR="/tmp/galardo-workers"
mkdir -p "$PID_DIR"

case "${1:-}" in
  start)
    echo "[fleet] launching $N parallel workers -> $API (prefix=$PREFIX)"
    for i in $(seq 1 "$N"); do
      NAME="${PREFIX}$(printf '%02d' "$i")-${HOSTNAME:0:8}"
      if [ -f "$PID_DIR/$NAME.pid" ] && kill -0 "$(cat "$PID_DIR/$NAME.pid")" 2>/dev/null; then
        echo "  $NAME already running (pid $(cat "$PID_DIR/$NAME.pid"))"
        continue
      fi
      ( cd "$WORKER_DIR" && GALARDO_WORKER_EXPERTISE="distributed-k6-fleet$i" \
        nohup python3 worker_daemon.py --api "$API" --name "$NAME" \
        > "/tmp/galardo-$NAME.log" 2>&1 & echo $! > "$PID_DIR/$NAME.pid" )
      echo "  started $NAME (pid $(cat "$PID_DIR/$NAME.pid"))"
      sleep 0.5
    done
    echo "[fleet] done. Verify: ./fleet-launch.sh status $API"
    ;;
  stop)
    echo "[fleet] stopping workers (prefix=${2:-w})..."
    for f in "$PID_DIR"/*.pid; do
      [ -f "$f" ] || continue
      NAME=$(basename "$f" .pid)
      case "$NAME" in ${2:-w}*) ;; *) continue;; esac
      kill "$(cat "$f")" 2>/dev/null && echo "  stopped $NAME" || echo "  $NAME not running"
      rm -f "$f"
    done
    ;;
  status)
    curl -s "$API/api/v1/workers" -o /tmp/galardo_workers.json
    python3 "$(dirname "$0")/fleet_status.py"
    ;;
  *) echo "usage: fleet-launch.sh {start <api> <n> [prefix] | stop [prefix] | status <api>}"; exit 2 ;;
esac
