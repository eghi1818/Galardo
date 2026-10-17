# GALARDO — SERVER SPEC: Proper & Maximal Deployment

Dokumen ini menjawab draf Improvement.md dengan spesifikasi final, dikalibrasi
terhadap **data pengukuran nyata** program ini (bukan teori): 10 run produksi/lab,
puncak **1.988 rps / 359K request / 901 MB traffic**, dan beban k6 500 VU churn.

---

## 1. Konsep Topologi (yang sering keliru draf awal)

**Control plane ≠ Generator beban.** Keduanya punya kebutuhan berbeda dan TIDAK
boleh digabung di satu mesin saat beban maksimal:

```
┌────────────────────────────┐         ┌─────────────────────────────┐
│  SERVER A — CONTROL PLANE  │         │  SERVER B — LOAD GENERATOR  │
│  Dashboard + API + DB      │  HTTP   │  worker daemon + k6         │
│  VictoriaMetrics + Evidence│ ◄─────► │  (identitas fleet terdaftar)│
│  audit log + webhook out   │ claim/  │  INI yang makan CPU+socket  │
│  butuh: disk stabil, RAM   │ ACK     │  butuh: CPU core, FD limit  │
└────────────────────────────┘         └─────────────────────────────┘
```

Draf awal mencampur semuanya ("Dasbor + VictoriaMetrics + armada worker k6" di
satu mesin) — saat 500 VU churn, generator akan memakan CPU dan dashboard/DB
ikuti tersendat. Pisahkan. (Blueprint §8 sudah mensyaratkan ini.)

## 2. Spesifikasi Hardware — Server A (Control Plane)

| Komponen | Minimum | **Rekomendasi (Proper)** | Alasan (dari data kita) |
|---|---|---|---|
| CPU | 4 core | **8 core / 16 thread** (Xeon E-2300, Ryzen 7/9, Apple M-series) | API + probe + safety controller + evidence build (tar.gz hashing 901 MB) |
| RAM | 16 GB | **32 GB DDR4/DDR5 ECC** | State JSON + telemetry ring + evidence in-memory; 32 GB memberi headroom 10x |
| Storage | 500 GB NVMe | **1 TB NVMe (RAID 1)** | Evidence ~1 MB/run kecil, tapi **audit.jsonl append-only + webhook deliveries + log tumbuh terus**; RAID 1 demi integrity bukti (PRD FR-9) |
| Network | 1 Gbps | 1 Gbps (control plane CUKUP 100 Mbps) | Control plane hanya JSON kecil — bukan jalur traffic |
| OS | — | Ubuntu 22.04 LTS / Debian 12 | Sesuai draf; LTS = patch stabil |

**Catatan perbaikan draf**: draf menyebut "VictoriaMetrics" — stack saat ini
belum memakainya (telemetry in-process). VM baru relevan di fase >10 worker.
Spec di atas sudah mencakup itu bila diaktifkan.

## 3. Spesifikasi Hardware — Server B (Load Generator, per VM)

**Ini komponen paling menentukan kapasitas generator.** Data kita: 1 MacBook
mentok ~450 rps churn; k6 keep-alive jauh lebih efisien.

| Komponen | Minimum | **Rekomendasi** | Alasan |
|---|---|---|---|
| CPU | 4 core | **8 vCPU dedicated** (bukan shared/burst) | k6 event-loop + TLS handshake churn makan CPU per koneksi |
| RAM | 8 GB | **16 GB** | ~20 KB/VU; 5000 VU ≈ 100 MB + overhead Go runtime |
| Storage | 50 GB SSD | 100 GB SSD | Log + output k6 |
| Network | 1 Gbps | **1–2 Gbps + IP publik dedicated** | 453 rps × ~1 KB respons = kecil; yang penting **connection rate** dan port ephemeral |
| jumlah VM | 1 | **2–4 VM** (region sama dgn origin) | 500–1000 VU per VM realistis; 2 VM = 1K VU, 4 VM = 2K+ |

**Perkiraan kapasitas generator per VM (8 vCPU)**: ~2.000–3.000 VU keep-alive,
~500–1.000 rps churn (TLS handshake per request itu mahal).

## 4. OS Tuning — WAJIB sebelum load (SYSCTL + LIMITS)

Ini bagian yang draf sebut sekilas — berikut nilai konkritnya, terkalibrasi
untuk churn 2000+ rps:

```bash
# /etc/sysctl.d/99-galardo.conf  (server B — generator)
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
fs.file-max = 2097152
vm.swappiness = 10

# /etc/security/limits.conf
*  soft  nofile  655350
*  hard  nofile  655350
root soft nofile 655350
root hard nofile 655350
```

```bash
# systemd override utk worker daemon (limits.conf TIDAK berlaku utk systemd service)
mkdir -p /etc/systemd/system/galardo-worker.service.d
cat > /etc/systemd/system/galardo-worker.service.d/limits.conf <<'EOF'
[Service]
LimitNOFILE=655350
LimitNPROC=65535
EOF
systemctl daemon-reload
```

Server A (control plane): cukup `nofile 65535` + `somaxconn 4096`.

## 5. Deployment Stack (Docker Compose, sesuai draf)

```
galardo/
├── docker-compose.yml        # api, dashboard (nginx), worker, (opsional: nats, victoriametrics)
├── .env                      # GALARDO_API_PORT, GALARDO_TARGET_ORIGIN, GALARDO_NATS_URL
├── deploy/
│   ├── sysctl/99-galardo.conf # tuning di atas (Dipasang di HOST, bukan container)
│   └── systemd/galardo-worker.service
```

Urutan migrasi (sesuai Improvement.md §3):
1. Validasi keep-alive toggle + metric fixes di lokal (✅ selesai di sesi ini)
2. Provision Server A → `docker compose up -d` → smoke 30s @ 10 rps
3. Provision Server B → install k6 + worker daemon (systemd) → register → fleet smoke
4. Rehearsal full: saturation ramp 50→500 rps dari Server B → bandingkan vs data MacBook
5. Baru jalankan Run 2b produksi (ramp setara Run 1) dari server fisik

## 6. Yang SUDAH dikerjakan dari Improvement.md (sesi ini)

- [x] **A1 Keep-Alive toggle**: scenario schema `keep_alive: true|false` + env
      `GALARDO_KEEP_ALIVE` — memisahkan kegagalan churn vs kapasitas. Tested inspect OK.
- [x] **B1 p50 fallback**: dashboard tampilkan `avg` + label "p50 n/a — avg ms
      (failed>50%)" ketika k6 median invalid.
- [x] **B2 Insights fix**: failed_rate >20% → CRIT/WARN "connection/timeout
      saturation"; "No degradation" tidak bisa lagi muncul saat failed tinggi;
      "Estimated safe capacity" ditolak bila run tidak bersih. Terverifikasi pada
      data Run 2 (96,2% failed → sekarang [CRIT], bukan [OK]).
- [x] **A2 Socket tuning**: nilai sysctl/limits konkret di dokumen ini (belum di-
      integrasikan ke Docker deployment script — butuh server fisik dulu).

## 7. Yang BELUM / butuh keputusan

- Docker Compose file final (keputusan STEP-68: NATS aktif tapi opt-in (GALARDO_NATS_URL); polling tetap default)
- VictoriaMetrics/OTel pipeline (relevan saat fleet >10 worker)
- Backup strategy Server A (audit + evidence adalah artefak kepatuhan)
