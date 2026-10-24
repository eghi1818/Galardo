# HASIL-147 — URL crt.sh + ekspektasi tes diperbaiki; verify_netssl_wired dibongkar

- tanggal: 2026-10-24 12:36
- BUG: CRT memakai '%%25' di format % sehingga Python melempar ValueError -> live test SKIP dan endpoint 500
- perbaikan: URL dibangun sebagai CRT_PREFIX + domain + CRT_SUFFIX
- BUG tes: fixture 'jelek..' dinormalisasi jadi 'jelek' tapi tidak ada di daftar harapan -> 1 cek gagal; diperbaiki
- verify_netssl_wired: rc=1 (lihat .out/STEP-147-netssl.txt)
- origins rc=0 | netssl rc=1 | test rc=0 | gate rc=2 | endpoint=200
