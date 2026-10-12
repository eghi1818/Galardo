# GALARDO — Multi-Region Fleet Deployment (AWS/GCP, secondary IP)

**Skrip:** `deploy_fleet.sh` — provisioning & launch worker daemon di N VM multi-region
**Prasyarat:** k6 terpasang di tiap VM, akses SSH, Galardo API dapat dijangkau worker

## Arsitektur

```
                orchestrator (laptop/VPS):8090
                       │  HTTP polling (claim/ack/heartbeat)
    ┌──────────┬───────┴────┬──────────┐
    ▼          ▼            ▼          ▼
 w-jkt-1   w-sgp-1..2   w-us-1..2   w-eu-1     (secondary/alias IP resmi dari akun cloud Anda)
 Jakarta   Singapore    US-East     EU-West
 (ENI secondary IP / GCP alias range: 8-16 IP per VM → edge-path identity diversity)
```

- Setiap VM: 1 worker daemon + k6. Kapasitas nyaman: 1.5–2.5k VU per VM (4 vCPU).
- **Secondary IP** (AWS ENI / GCP alias) memberi keberagaman source IP dari akun
  Anda sendiri — bukan proxy. Source-identity registry tercatat per worker.
- Firewall origin: allowlist IP publik VM + secondary IP (direct path, opsional).

## Deploy (ringkas)

```bash
# 1. daftarkan fleet (dijalankan sekali)
GALARDO_API=http://ORCH:8090 ./deploy_fleet.sh register w-jkt-1 w-sgp-1 w-sgp-2 w-us-1 w-us-2 w-eu-1

# 2. di tiap VM (SSH):
GALARDO_API=http://ORCH:8090 nohup python3 worker_daemon.py --api $GALARDO_API --name w-jkt-1 &

# 3. verifikasi: semua worker IDLE di dashboard > Workers
# 4. jalankan job bertanda k6 (plan.remote_dispatch + config remote-dispatch enabled)
```

## Secondary IP (AWS contoh)

```bash
aws ec2 assign-private-ip-addresses --network-interface-id eni-xxx \
  --secondary-private-ip-address-count 8
# EIP per secondary IP bila perlu publik → daftarkan ke worker capabilities:
#   capabilities: ["src-ip:203.0.113.10", ...] (source-identity registry)
```

GCP:
```bash
gcloud compute instances network-interfaces update w-jkt-1 \
  --network-interface=subnet=default,aliases=10.0.0.0/28
```

## Source-Identity Registry

Worker melaporkan IP publik + secondary IPs saat register (`capabilities`:
`src-ip:<addr>`). Orchestrator menyimpan registry; telemetry run dapat
dikelompokkan per source-IP-group untuk analisis distribusi LB edge Anda.

## Security

- API orchestrator: TLS + token (jangan expose publik tanpa auth — BLOCKER Prolog §6)
- VM worker: non-root, egress hanya ke target + orchestrator
- k6 pinned version; workerDaemon memverifikasi presence k6 saat start
