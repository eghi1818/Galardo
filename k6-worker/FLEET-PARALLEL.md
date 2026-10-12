# GALARDO — Fleet Parallel Deployment Guide (Server B)

Panduan menyiapkan **2–4 worker k6 paralel** di Server B (load generator) sesuai
topologi SERVER-SPEC.md, plus bukti demo paralelisasi lokal.

## Yang sudah terbukti (demo lokal, 2026-10-12)

- 3 worker daemon paralel (`w01/w02/w03-Eghis-Ma`) diluncurkan via `fleet-launch.sh`
- Job 1000 rps spike (180s) diklaim oleh **salah satu** worker (race claim aman):
  `w03-Eghis-Ma` menang → **179.947 req @ 1.000 rps, failed 0,1%** → RECOVERED
- Evidence VERIFIED: `SHA 5406b7987d264849…` (11 file)
- Worker lain tetap IDLE — tidak tumpang tindih, tidak double-execution

## Setup Server B (provisioning baru)

```bash
# 1. Base (Ubuntu 22.04/Debian 12): k6 + python3 + tuning kernel
#    -> ikuti SERVER-SPEC.md §4 (sysctl + limits + systemd override)

# 2. Copy galardo/ ke /opt/galardo (backend + k6-worker)

# 3. Install systemd unit template
cp k6-worker/galardo-worker@.service /etc/systemd/system/
systemctl daemon-reload

# 4. Nyalakan N worker paralel (satu unit per worker)
systemctl enable --now galardo-worker@w11-jkt-1.service
systemctl enable --now galardo-worker@w12-jkt-1.service
systemctl enable --now galardo-worker@w13-jkt-1.service   # dst...
```

Atau tanpa systemd (testing/dev): `./fleet-launch.sh start http://ORCH:8090 4 w`

## Distribusi beban — bagaimana cara kerjanya

1. Semua worker **polling claim** dengan interval 2s; orchestrator menjamin
   **satu job hanya diklaim satu worker** (single-claim guard di state machine).
2. Worker yang menang: RUNNING; yang lain lanjut IDLE untuk job berikutnya.
3. Job harus ditandai `remote_dispatch: true` pada plan + config
   `remote-dispatch` aktif di orchestrator (dua opt-in, sesuai desain).
4. Fail-closed: worker yang kehilangan koneksi kontrol >20s membunuh k6-nya
   sendiri (watchdog) — job tidak pernah "hilang" tanpa jejak.

## Distribusi beban merata antar worker

Orchestrator saat ini meng-assign **satu job ke satu worker** (kecuali fleet
mencapai ratusan job). Untuk memecah SATU job besar ke beberapa worker sekaligus
(distributed single-test), itu fase berikutnya: orchestrator memecah skenario
menjadi N shard (mis. 500 rps × 4 worker) — skeleton sudah ada di WORKER-SPEC.md.

## Load distribution ke origin

Dengan N VM × ~1.000 rps churn per VM, generator mencapai N×1.000 rps aggregate.
Socket tuning per VM (SERVER-SPEC.md §4) wajib sebelum load.

## Security checklist per VM

- [ ] Egress hanya ke: target + orchestrator (security group / ufw)
- [ ] Worker jalan non-root (user `galardo`)
- [ ] k6 version pinned sama di semua VM
- [ ] NTP aktif (telemetry timestamps)
- [ ] Akses SSH: key-only, no password
