# HASIL-120 — auth menyala; UI, suite, dan verifier semuanya memakai token

- tanggal: 2026-10-22 21:33
- GALARDO_REQUIRE_AUTH=1 + token acak; dashboard punya kotak token localStorage
- sitecustomize.py (root/tools/tests/backend): suntik Authorization ke urllib + http.client
- gate menjalankan docker compose stop galardo agar port 8090 bebas untuk app verifier
- verify_ladder_api.py: token dibaca dari .env, di-mirror ke env app, dan dikirim di api()
- port compose ter-bind ke 127.0.0.1; backup data/ di .out/backup/

## Bukti
- gate: 37 verifier hijau / 0 GAGAL
- test: RESULTS: 82 passed, 0 failed, 1 skipped
- ladder: HASIL: 18 passed, 0 failed
- auth: overview tanpa token 401, dengan token 200

## Akar masalah (5, semuanya terdiagnosis bukan tebakan)
1. shim fallback dev-token vs token .env -> 401
2. sitecustomize tidak dimuat (sys.path[0] disisipkan setelah site.py) -> PYTHONPATH=.
3. container memegang 8090 -> verifier menghantam container, bukan app yang ia boot
4. verifier ladder setel token sendiri -> token di-mirror
5. sisipan os.environ.update salah tempat -> pre-commit menolak; file itu tanpa def boot()

## Sisa opsional
- TLS via Caddy bila diekspos ke internet; GALARDO_POOL_* bila mau bukti lane rotate
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
