# CHECKLIST KREDENSIAL anyip.io (Mode B - single gateway)

Tujuan: membuktikan ROTASI EGRESS NYATA (bukan klaim). Mode B = satu gateway, rotasi di sisi penyedia.

## 1. Yang perlu diisi di .env (hanya ini)
GALARDO_GATEWAY_URL=<skema>://<user>:<pass>@<host>:<port>
# opsional:
GALARDO_GATEWAY_STICKY=worker
GALARDO_GATEWAY_POOL=anyip
GALARDO_PROXY_POOL=anyip

Catatan: GALARDO_GATEWAY_URL menerima bentuk host:port, user:pass@host:port, scheme://..., socks*.

## 2. Setelah diisi
pkill -f run_local.py
make gate
python3 tools/verify_egress_rotation.py

Bukti lulus = keluaran memuat IP unik >= 2 dari endpoint egress (bukan satu IP).
Kalau IP unik = 1 -> sticky salah / gateway meneruskan IP asal; catat sebagai divergensi, jangan diakali.

## 3. Yang TIDAK perlu dibuktikan lagi (sudah hijau)
rantai pool->transport (verify_egress_wired), gateway parse/masking (verify_gateway),
egress recorder (verify_egress_record), intel/checkhost/multilane/tunnel.
