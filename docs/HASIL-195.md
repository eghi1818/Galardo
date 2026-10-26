# HASIL-195 - origins tahan crt.sh tumbang + resolve IP + baseline 2 target

- tanggal: 2026-10-26
- AKAR 1: backend/origins.py:97 fetch_crt tidak menangkap HTTPError. crt.sh membalas 404 untuk
  waspadaweb.com sehingga handler origins jatuh ke 500. (Untuk wecash.ai crt.sh membalas 200.)
- AKAR 2: backend/api.py:762 memanggil origins.candidates(..., resolve_hosts=False) sehingga semua
  host ber-ips kosong -> penemuan origin tidak berguna.
- AKAR 3: verify_origins.py cek live rapuh. Sebelumnya CT gagal = melempar = tertangkap except =
  skip (hijau). Setelah CT gagal ditangani, cek jumlah>=1 berubah jadi GAGAL. Verifier itu hijau
  karena kebetulan error-nya tertangkap, bukan karena perilakunya benar.
- FIX:
  1. candidates(): fetch_crt dibungkus try/except; bila CT tumbang hosts kosong lalu diisi cadangan
     {domain, www.domain} supaya tetap ada kandidat.
  2. api.py: origins memakai resolve_hosts=True, limit=40 (IP terisi).
  3. verify_origins.py: cek live jadi toleran + uji baru "CT tumbang tidak membuat candidates()
     melempar" via monkeypatch fetch_crt.
- BASELINE (saksi 2, check-host.net 4 node): wecash.ai HIDUP 4/4 negara; waspadaweb.com 3 hidup /
  0 mati / 1 belum. Disimpan di docs/BASELINE-TARGET.md.
- angka: hijau rc=0, verifier=65, cek=465, merah=tidak ada
