# HASIL-151 - pool default dari env jadi FAKTA + verifier egress_wired behavioral

- tanggal: 2026-10-24 17:57
- KOREKSI ATAS HASIL-150: STEP-150 TIDAK hijau (wired rc=1, gate rc=2) tetapi commit 7f83fdf berlabel "terbukti"
- AKAR 1 (nyata): proxy.py TIDAK membaca GALARDO_PROXY_POOL -> klaim STATUS + pelajaran 20 masih hipotesis
- AKAR 2 (artefak): cek teks "transport.set_proxy(" tidak cocok karena kode pakai getattr(transport,"set_proxy")
- FIX: proxy.py dapat _default_pool() + self.pool = pool if pool is not None else _default_pool()
- FIX: tools/verify_egress_wired.py ditulis ulang BEHAVIORAL (FakeTransport, cek efek bukan teks)
- angka: wired rc=1 | record rc=0 | test rc=0 | gate rc=2
