# HASIL-150 — bukti rantai pool->transport + probe egress on demand

- tanggal: 2026-10-24 15:32
- TEMUAN: jalur sudah ada dan OTOMATIS — proxy.py:62 resolve pool dari GALARDO_PROXY_POOL, boot menyetelnya ke 'gateway', transport punya set_proxy; proxypool punya fungsi pasang proxy ke transport
- tools/verify_egress_wired.py: bukti offline rantai itu (resolve pool gateway -> fungsi pasang memanggil transport.set_proxy dengan endpoint gateway)
- endpoint /egress/status?probe=1: ambil IP egress nyata saat diminta lalu catat
- KOREKSI: verify_egress_record sebenarnya 12 cek (HASIL-149 menulis 13)
- egress_wired rc=1 | egress_record rc=0 | test rc=0 | gate rc=2
