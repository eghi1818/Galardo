# HASIL-165 - multi-lane di engine (transport per-lane per-VU)

- tanggal: 2026-10-24
- TEMUAN: engine memakai SATU self.transport bersama semua VU (engine.py:253/:300) -> set_proxy pada
  transport bersama akan saling menimpa antar VU (balapan). Jadi multi-lane butuh transport per-lane.
- ISI (aditif, default lama TIDAK berubah): param `lanes=None`; VU memilih lanes[vu_id % n];
  transport khusus lane dibuat sekali + set_proxy(lane.endpoint()); _do_request(req, tr=None);
  run() menutup transport lane + melaporkan lanes.hits. Tanpa lanes -> hasil["lanes"] is None.
- VERIFIER: tools/verify_multilane.py behavioral (target http.server lokal, 18 cek): regresi tanpa
  lane, sebaran round-robin ke 2 lane, satu transport per lane, set_proxy terbukti terpanggil
  (scan atribut transport), _do_request memakai transport yang diberikan.
- angka: ml rc=0 | knee rc=0 | live rc=0 | ch rc=0 | pages rc=0 | test rc=0 | gate rc=0
