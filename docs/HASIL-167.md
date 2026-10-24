# HASIL-167 - instrumentasi penentu (bukti: _do_request jalan 4419x)

- tanggal: 2026-10-24
- BUKTI: log _do_request masuk=4419 ok=4419, vu_errors=[], kunci vars transport lane == transport utama,
  TETAPI window.requests = 0. Jadi bukan bug lane/sebaran/transport.
- TEMUAN: TelemetryRing.window(N) dihitung relatif ke jam dinding saat dipanggil; run() punya ekor
  wind-down (duration_actual 2.52s utk uji 1.5s) -> jendela 1.5s kosong. Ini juga sebab flaky STEP-165.
- KOREKSI JUJUR: _start_lane (STEP-166) sebenarnya NO-OP karena Transport tak punya start/open/warmup;
  dan set_proxy memang satu argumen (set_proxy(self, proxy)) -> jalur proxy lolos lewat fallback.
- TAMBAHAN yang dipertahankan: _vu_aman + vu_errors di engine (VU tidak boleh mati sunyi).
