# HASIL-148 — patuhi aturan netssl (urlopen wajib pakai context)

- tanggal: 2026-10-24 12:49
- TEMUAN verify_netssl_wired (BENAR): origins.py:87 memakai urlopen tanpa SSL context. Aturan proyek: semua fetch HTTPS di backend wajib lewat netssl.context() karena bundle CA sistem bisa tidak valid.
- perbaikan: origins.py import netssl level modul + context pada urlopen; gateway.py HTTPSHandler memakai context netssl (meski tidak ditandai verifier, tetap dipatuhi)
- netssl rc=0 | origins rc=0 | gateway rc=0 | test rc=0 | gate rc=0
