# HASIL-193 - akar sesungguhnya: data/state.json rusak + penulisan tidak atomik

- tanggal: 2026-10-26
- AKAR: dua proses menulis data/state.json bersamaan -> JSONDecodeError: Extra data (ekor 357 byte)
  -> app crash saat boot (backend/db.py:65 json.load) -> verify_devup.py dan verify_headers.py MERAH.
  Keduanya boot app sendiri lewat make dev-up dan jujur melaporkan gagal (bukan bug verifier).
- FIX:
  1. data/state.json diperbaiki (dokumen JSON pertama disimpan; cadangan .out/rusak-state.json-*.bak)
  2. backend/db.py: _baca_toleran (pulih dari ekor rusak + cadangkan ke .rusak) dan _dump_ke
     (tulis ke .tmp lalu os.replace = atomik) supaya tidak bisa terulang
  3. tools/verify_state_valid.py: kunci baru - validasi SEMUA *.json + sifat toleran/atomik db.py
  4. runner diberi trap HUP supaya tidak mati saat tab ditutup
  5. aturan baru: blok tempel wajib bebas karakter tanda seru
- angka: verifikasi rc=2 | hijau rc=2 | state_valid rc=0 | patch_ok=1
- ANGKA KANONIK: verifier=65 | total cek hijau=239 | merah=tidak ada
