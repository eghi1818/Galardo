#!/usr/bin/env bash
# Galardo - siapkan & verifikasi di VPS. Jalankan DI VPS setelah repo disalin.
# Idempoten: hanya memeriksa, tidak merusak. Tidak menyimpan kredensial.
set -u
cd "$(dirname "$0")/.." || exit 1
RC=0

echo "== GALARDO DEPLOY VPS =="
echo "host : $(hostname) | $(uname -srm)"
echo "repo : $(pwd)"
echo "HEAD : $(git log --oneline -1 2>/dev/null)"
echo

echo "-- 1. prasyarat --"
for bin in python3 git curl; do
  if command -v "$bin" >/dev/null 2>&1; then echo "  ok   $bin: $($bin --version 2>&1 | head -1)"; else echo "  HILANG $bin"; RC=1; fi
done
PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)"
case "$PYV" in 3.1[0-9]|3.[2-9][0-9]) echo "  ok   python $PYV";; *) echo "  PERINGATAN python $PYV (butuh >= 3.10)"; RC=1;; esac
if command -v cloudflared >/dev/null 2>&1; then echo "  ok   cloudflared ada"; else echo "  info cloudflared belum ada (untuk make tunnel)"; fi
echo

echo "-- 2. .env (yang wajib ada) --"
if [ -f .env ]; then
  for k in GALARDO_REQUIRE_AUTH GALARDO_DEV_TOKEN GALARDO_ADMIN_PASSWORD GALARDO_MULTILANE; do
    if grep -q "^$k=" .env; then echo "  ok   $k"; else echo "  HILANG $k"; RC=1; fi
  done
  if grep -q "^GALARDO_GATEWAY_URL=..*" .env; then echo "  ok   GALARDO_GATEWAY_URL (anyip)"; else echo "  info GALARDO_GATEWAY_URL belum diisi (rotasi egress belum bisa dibuktikan)"; fi
else
  echo "  HILANG .env (salin dari mesin lokal, jangan commit bila berisi kredensial)"; RC=1
fi
echo

echo "-- 3. port 8090 --"
if command -v lsof >/dev/null 2>&1; then
  if lsof -nP -iTCP:8090 -sTCP:LISTEN >/dev/null 2>&1; then echo "  info port 8090 sudah dipakai"; else echo "  ok   port 8090 bebas"; fi
fi
echo

echo "-- 4. verifikasi wajib (jangan lewat) --"
make verifikasi > .out/deploy-vps-verifikasi.txt 2>&1; rv=$?
echo "  verifikasi rc=$rv (SEMUA tools/verify_*.py)"
make gate > .out/deploy-vps-gate.txt 2>&1; rg=$?
echo "  gate rc=$rg"
make test > .out/deploy-vps-test.txt 2>&1; rt=$?
echo "  test rc=$rt"
tail -2 .out/deploy-vps-test.txt
[ "$rv" = "0" ] && [ "$rg" = "0" ] && [ "$rt" = "0" ] || RC=1
echo

echo "-- 5. langkah berikutnya --"
echo "  a) jalankan app:   nohup python3 run_local.py > .out/app.log 2>&1 &   (dari folder backend)"
echo "  b) buka ke pihak ketiga: make tunnel"
echo "  c) bukti rotasi:   python3 tools/verify_egress_rotation.py   (harus IP unik >= 2)"
echo "  d) bukti beban:    ikuti docs/TARGET-BUKTI.md (wecash.ai, waspadaweb.com)"
echo
if [ "$RC" = "0" ]; then echo "SIAP: prasyarat lengkap."; else echo "BELUM SIAP: perbaiki item di atas dulu."; fi
exit "$RC"
