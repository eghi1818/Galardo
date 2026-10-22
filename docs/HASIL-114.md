# HASIL-114 — item 2/3 lane proxy + item 4 label multi-lane

- tanggal: 2026-10-22 13:28
- verifier tools/verify_lane_proxy.py: RESULTS: 48 passed, 0 failed
- gate: rc=0 (     337 baris bukti)
- test: RESULTS: 82 passed, 0 failed, 1 skipped

## Yang dibangun
- backend/proxy.py: Lane + LaneRegistry. direct = default; rotate/residential opt-in via set_mode().
- Statistik per lane terpisah dari statistik target (LaneRegistry.status(target=...)).
- Transport._lane_endpoint() + precedence pada effective_proxy: eksplisit > lane aktif > self.proxy.
- Transport._label_lane(): response.lane = evidence lane (item 4); slot 'lane' di Response.
- api.py: GET /lanes (VIEWER), POST /lanes/mode (TEST_OPERATOR).
- Tanpa kredensial pool, lane jatuh ke koneksi langsung (fail-open).

## Bug yang dibuka verifier (3)
1. Response memakai __slots__ -> response.lane ditolak AttributeError; slot 'lane' ditambah + default None.
2. set_mode(rotate) tidak berpengaruh: effective_proxy hanya dari proxy eksplisit/self.proxy -> _lane_endpoint().
3. Makefile: gate sudah meng-glob tools/verify_*.py; sisipan manual dibuang.

## Bukti kunci
- mode direct: kunci cache ConnectionPool identik antar request (keep-alive utuh).
- mode rotate: dial memakai endpoint pool, label lane rotate/egress proxy.
- proxy eksplisit tetap menang atas mode lane.
- transport tanpa registry: tanpa label (nol regresi).
