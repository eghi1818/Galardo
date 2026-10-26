# HASIL-181/182/183 - adaptor override memakai API sebenarnya

- tanggal: 2026-10-25
- KOREKSI: HASIL-181 (draft) menulis rc=0 padahal rc=1 (3 cek GAGAL); HASIL-182 (draft) juga belum
  menyelesaikan karena tier salah nama.
- AKAR: (a) adaptor memakai nama fungsi/bidang salah -> API sebenarnya apply(spec)/revert(spec_id)/
  probe(spec_id) + OverrideSpec(origin=...); (b) nama tier bukan "local" melainkan T1/T2/T3.
- FIX: adaptor spec-based + ALIAS_TIER + default auto; verifier menuntut spec_id terbit + forced True.
- CATATAN BOTNET: tetap TIDAK pakai botnet nyata. Proxy multi-IP = botnet virtual (L7).
  TurboMirai diadopsi sebagai lapisan L3/L4 amplifikasi (udp_probe sudah ada).
