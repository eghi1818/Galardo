# HASIL-152 - cek transport dibetulkan (method vs fungsi modul); egress_wired hijau

- tanggal: 2026-10-24 18:12
- KOREKSI: cek "transport punya set_proxy" memakai hasattr() di level modul, padahal set_proxy
  adalah METHOD di dalam class (transport.py:300 def set_proxy(self, proxy)). 9/10 cek lain sudah hijau.
- FIX: cek transport jadi AST (cari def set_proxy di mana pun) + behavioral best-effort
  (instansiasi objek transport nyata lalu buktikan proxypool.apply benar-benar menyetel endpoint gateway)
- KONFIRMASI: patch STEP-151 di proxy.py terbukti (_default_pool baris 34, self.pool = pool if pool is not None else _default_pool() baris 59)
- angka: wired rc=0 | record rc=0 | test rc=0 | gate rc=0
