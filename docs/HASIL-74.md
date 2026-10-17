# HASIL-74 — P0.1b: urlopen telanjang (tanpa netssl.context)

Status: TUTUP.

## Temuan (P0, dari STEP-55, diverifikasi ulang di sini)
Empat modul keluar ke HTTPS lewat urllib.request.urlopen TANPA context, sehingga memakai
SSL context bawaan (CA sistem) dan mengabaikan GALARDO_CA_FILE/certifi:
    backend/ownership_ladder.py:87
    backend/webhooks.py:94
    backend/worker_daemon.py:62
    backend/run_local.py:61
Modul yang sudah benar sebelumnya: netssl.py, knee_probe.py, otlp.py, step_load.py.

## Perbaikan
- Keempat modul: `import netssl as _ns` di level modul + `context=_ns.context()` pada urlopen.
- verifier verify_netssl_wired.py bagian E: memindai SEMUA backend/*.py; setiap baris
  `urlopen(` yang tidak memuat `context=` dianggap pelanggaran (netssl.py dikecualikan).
- verifier bagian E2: AST — `netssl`/`_ns` harus Import di level modul (bukan di dalam docstring).
- fetch HTTPS nyata: ownership_ladder.default_fetcher("https://example.com/") -> status 200.

## Insiden yang ketangkap (jujur)
Percobaan pertama menempelkan `import netssl as _ns` DI DALAM docstring run_local.py
(loop berhenti di baris 1 karena docstring bukan import/komentar). py_compile lulus,
tetapi import-nya tidak pernah dieksekusi -> wait_http() kena NameError yang ditelan
`except Exception` -> dev-up selalu kehabisan deadline dan `GET /api/v1/health` -> 000.
Perbaikan: import dipindah ke setelah docstring + penjaga AST (E2).

## Bukti
    ownership_ladder.py import level modul: ['_ns', ...] -> OK
    webhooks.py / worker_daemon.py / run_local.py -> OK
    dev-up: tunggu 1: 000 ; tunggu 2: 200
    smoke.sh: [v] GET /api/v1/health -> 200 ; == SMOKE OK ==
    verify_netssl_wired.py -> RESULTS: 20 passed, 0 failed
    verify_db_pg.py -> 46 passed, 0 failed ; make test -> 79 passed, 0 failed

## Kenapa lolos selama ini
verify_netssl_wired bagian D hanya memindai pemanggil create_default_context; urlopen
polos tak pernah diperiksa. Sekarang diperiksa, termasuk lewat AST.
