#!/bin/bash
REPO="/Users/eghi/Documents/REPO/Galardo/Galardo-main"
cd "$REPO" || { echo "REPO TIDAK ADA: $REPO"; exit 1; }
P="$(pwd -P)"
[ "$P" != "$REPO" ] && { echo "SALAH REPO: $P (harus $REPO)"; exit 1; }
echo "GUARD OK: $P"
git log --oneline -1
echo "perubahan belum di-commit: $(git status --porcelain | wc -l | tr -d ' ')"
