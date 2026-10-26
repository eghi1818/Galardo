# HASIL-77 — Integrasi tool eksternal (Subfinder / Nikto / Traceroute)

Status: SELESAI. Fail-open: tool yang belum terpasang tidak mematikan Galardo.

## Peta ke GOAL
- subfinder  -> BYPASS/origin : enumerasi subdomain -> kandidat origin
- nikto      -> 404 & BLANK   : pemindaian web server -> temuan
- traceroute -> DOWN          : jejak hop + latensi

## Yang dibangun
- backend/exttool.py: registry tool, deteksi shutil.which, runner subprocess dengan
  timeout tegas (GALARDO_EXTTOOL_TIMEOUT, default 20s) + batas output 200 KB,
  parser keluaran -> JSON terstruktur (hops / subdomains / findings). Tidak melempar.
- Endpoint: GET /api/v1/exttools (VIEWER) dan POST /api/v1/exttools/<tool>/run
  (TEST_OPERATOR; body {args, target, timeout}); `args` wajib list -> 422 bila bukan.
- tools/verify_exttool.py: 16 cek (parser, fail-open, timeout, live traceroute).

## Bukti
    verify_exttool.py -> RESULTS: 16 passed, 0 failed
      termasuk: C tool hilang -> ok False + available False + alasan menyebut PATH
                E timeout dipatuhi (elapsed < 2.5s untuk timeout 1s)
                F live traceroute ke 127.0.0.1 -> hop >= 1, tidak menggantung
    HTTP nyata:
      GET /api/v1/exttools -> 200, traceroute available=true, subfinder/nikto available=false
      POST /exttools/traceroute/run -> ok=true, parsed hop >= 1
      POST /exttools/subfinder/run -> ok=false, available=false, reason menyebut PATH
      POST /exttools/ngawur/run -> 200 dengan daftar tool tersedia
      args bukan list -> 422
    make test -> 79 passed, 0 failed

## Catatan
Biner yang ADA di mesin ini: traceroute (+ dig). subfinder/nikto belum terpasang
(`brew install subfinder nikto`). Justru itu yang membuat jalur fail-open teruji nyata.
Panel dashboard untuk tool ini belum dibuat (kandidat langkah berikutnya).
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
