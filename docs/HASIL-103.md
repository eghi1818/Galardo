# HASIL-103 — koreksi status INVENTARIS + diagnosis V6

STEP: 103.

## Hasil audit tujuh item PENDING
Empat dari tujuh ternyata sudah ada kodenya, hanya tidak tercatat:
- item 10 DNS manipulation -> SEBAGIAN: quorum TXT, lapisan dns di layer_attrib, probe_spoof.
- item 13 UDP reflection -> SEBAGIAN: backend/udp_probe.py ter-wire di api.py:1378-1384.
- item 14 worm/lease -> SEBAGIAN: worker_daemon.py lease fail-closed + heartbeat.
- GOAL 2 observer tersambung -> SELESAI: tools/verify_goal2_wiring.py hijau di gate.
Benar-benar belum: item 9 botnet IoT global, item 2/3 lane proxy, item 4 transport multi-lane.

## Drift internal yang ditutup
Seksi E INVENTARIS menulis "T1 SEBAGIAN (RBAC+MFA, backup, Docker pending) | T2-T4 PENDING"
padahal tabel F di file yang sama mencatat 8a-8d SELESAI dan 9a-9d SELESAI.

## Yang diubah
- docs/INVENTARIS.md: status item 10/13/14 + GOAL 2 + seksi E dikoreksi dari kode & verifier;
  ditambah bagian Z (koreksi STEP-103).
- docs/SESSION_STATE.md dan docs/HANDOFF.md: daftar SISA dikoreksi - tulisan STEP-102
  ("sisa usul P7 + Tier 3-4") tidak lengkap; P7 = nama lain item 9.
- docs/PENDING.md: bagian "Sisa PRD" menunjuk INVENTARIS sebagai otoritatif.

## V6
Diagnosis dijalankan: bandingkan jumlah check() di setiap verifier dengan jumlah yang
benar-benar dilaporkan di baris RESULTS. Selisih ~4-5 menandai verifier yang punya check()
tidak pernah dieksekusi. Perbaikan kodenya jadi STEP berikut.

## Bukti
- make gate + make test: lihat .out/HASIL-103-gate.txt dan .out/HASIL-103-test.txt
- angka: rc=2 (belum dicatat blok ini; lihat HASIL-193)
