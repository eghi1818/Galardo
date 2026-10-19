# HASIL-97 — F-1b & F-24: dua flake terakhir (akar + tambalan)

STEP: 97
Tanggal: 2026-10-19
Status: TUTUP (F-1b, F-24)

## Ringkasan
Dua flake terakhir yang membuat gate/CI tidak bisa dipercaya ditutup PADA AKARNYA,
bukan dengan menaikkan jumlah retry.

## F-1b — dispatch 409 di tests_integration
Gejala: `FAIL: degraded-target job dispatched (async preflight DB checks PASS) — st=409`, ~17%.

Bukti forensik (log F1_DEBUG):
- percobaan #1 gagal HANYA pada cek `no conflicting active job` (konflik sesaat);
- percobaan #2..#60 gagal pada `job in state REJECTED, only PENDING can start`.

Akar: `orchestrator.start_job` memindahkan state ke `PREFLIGHT` (baris 358) lalu, saat preflight
gagal, menulis `REJECTED` TANPA membedakan cek mana yang gagal. Konflik sesaat karena itu
mengeksekusi job ke terminal -> retry 60x (30 s) sia-sia.

Tambalan (backend/orchestrator.py):
1. state yang boleh distart ulang: `PENDING` atau `PREFLIGHT` (retry idempoten);
2. bila SEMUA cek gagal = `no conflicting active job` -> set balik `PENDING` + tandai
   `retryable: YES`; bila ada cek mandatory lain -> tetap `REJECTED` (terminal);
3. `_conflicting_active_job` mencetak id+status pemblokir saat `F1_DEBUG`.

Tambahan (backend/api.py): respons `/start` menyertakan `retryable` (beda 409 "ulangi" vs
409 "perbaiki data").

Verifier pengunci: `tools/verify_start_reject.py` (9 cek, deterministik via monkeypatch
`run_preflight`): konflik -> retryable + tetap PENDING + retry sukses; gagal lain -> REJECTED;
`PREFLIGHT` bisa distart ulang.

## F-24 — uji MFA replay flake
Gejala: `FAIL: mfa: replay step sama ditolak — 200` (1x dalam 12 run setelah F-1b ditutup).

Akar: `tests/tests_integration.py` baris 515 memanggil `_mfa.totp(secret)` ULANG untuk request
replay lalu berasumsi step sama. Bila eksekusi melewati batas step TOTP (30 s), kodenya beda ->
`step > last_step` -> wajar 200. Server (`mfa.py`) sudah benar.

Tambalan: kode di-cache (`_c1`) dan dipakai untuk replay (dijamin step sama); diagnostik
`code_sama=`; debug `[mfa]` via env `MFA_DEBUG` untuk membedakan batas-step vs read-after-write.

## Hipotesis yang DISANGKAL (jujur)
- "job sisa di data/state.json" — disangkal 3x (suntikan job; isolasi `mkdtemp` per run).
- "kehabisan proses / fork" — disangkal: satu `make test` menambah ~0-3 proses, bukan ~1544.
  Angka blok 98 adalah artefak pengukuran; `ps -U` tidak menghitung thread.

## Bukti
- 42 run `make test` berturut-turut bersih (22 sebelum F-24 muncul, 20 sesudah ditutup).
  P(bersih kebetulan | flake 17%) ~ 0.0004.
- `make gate` rc=0 termasuk verifier baru.
- 6 proses `yes` nyangkut (umur 50 mnt) ditemukan & dibunuh; bukan dari repo.
