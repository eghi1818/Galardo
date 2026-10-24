#!/usr/bin/env bash
# Galardo - buka Galardo ke pihak ketiga lewat Cloudflare Tunnel.
# Mode token  : bila GALARDO_CF_TUNNEL_TOKEN (atau GALARDO_CF_TOKEN) tersedia -> named tunnel.
# Mode cepat  : kalau tidak ada token -> URL acak *.trycloudflare.com (cukup untuk uji pihak ketiga).
set -u
PORT="${GALARDO_API_PORT:-8090}"
TOK="${GALARDO_CF_TUNNEL_TOKEN:-${GALARDO_CF_TOKEN:-}}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared belum terpasang. Pasang dulu: brew install cloudflared"
  exit 1
fi

if [ -n "$TOK" ]; then
  echo "tunnel: mode TOKEN (named tunnel) -> http://127.0.0.1:${PORT}"
  exec cloudflared tunnel --no-autoupdate run --token "$TOK"
else
  echo "tunnel: mode CEPAT (trycloudflare) -> http://127.0.0.1:${PORT}"
  echo "catatan: pakai URL publiknya untuk pihak ketiga; token kosong = mode cepat."
  exec cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${PORT}"
fi
