#!/usr/bin/env bash
# Jalankan Galardo dev server terlepas dari terminal (tahan SIGHUP).
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p .out
trap '' HUP
exec make dev-up >> .out/app.log 2>&1
