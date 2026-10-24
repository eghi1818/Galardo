# HASIL-163 - check-host per-negara (modul + verifier + endpoint)

- tanggal: 2026-10-24
- TUJUAN: bukti target MATI/HIDUP dari banyak negara (langsung melayani GOAL Layer 7).
- ISI: backend/checkhost.py (parse_nodes/parse_hasil/grup_negara/ringkas/mulai/ambil/tunggu/probe;
  inti murni offline-testable, hanya jaringan di mulai/ambil; patuh aturan netssl) +
  tools/checkhost.py (CLI) + route POST /api/v1/checkhost (body {url,max_nodes}) + `make checkhost`.
- VERIFIER: tools/verify_checkhost.py (offline deterministik, fixture + monkeypatch _get_json) +
  tools/verify_checkhost_wired.py (AST wiring + behavioral).
- CATATAN PETA (STEP-162): lane SUDAH lengkap (proxy.py + /lanes + 4 verifier); yang kurang = engine
  belum memakai lane -> masuk langkah berikutnya.
- angka: ch rc=0 | chw rc=0 | intel rc=0 | live rc=0 | pages rc=0 | test rc=0 | gate rc=0
