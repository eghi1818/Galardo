# GALARDO — Webhook / Telemetry Hook API Documentation
**Status:** LIVE (terverifikasi E2E 2026-10-10) · **Base:** `http://<orchestrator>:8090/api/v1`

Forward event kontrol-plane (job lifecycle, safety aborts, evidence) ke sistem
monitoring/analytics milik Anda — Grafana/Datadog/SIEM/webhook umum. **Data export
saja**: hook tidak memiliki kemampuan routing traffic (batas PRD addendum tetap).

## Endpoints

| Method | Path | Fungsi |
|---|---|---|
| POST | `/webhooks` | register hook `{name, url, secret, events[]}` |
| GET | `/webhooks` | daftar hook |
| DELETE | `/webhooks/{id}` | nonaktifkan hook |
| POST | `/webhooks/{id}/test` | kirim event `hook.ping` uji |
| GET | `/webhooks/deliveries` | 100 delivery terakhir (ok/attempts/latency) |

## Event types

`job.completed` · `job.aborted` · `job.failed` · `job.recovery` (reserved) ·
`safety.abort` (reserved) · `evidence.created` · `hook.ping`

## Payload format

```json
POST <url-anda>
X-Galardo-Event: job.completed
X-Galardo-Delivery: dlv-xxxxxxxx
X-Galardo-Signature: sha256=<hex>

{"event": "job.completed", "sent_at": "2026-10-10T09:20:53.123Z",
 "data": {"job_id": "job-…", "status": "COMPLETED", "plan": "plan-…",
          "abort_code": null, "started_at": "…", "ended_at": "…",
          "correlation_id": "…"}}
```

Untuk `evidence.created`: `{evidence_id, job_id, bundle_sha256, manifest_sha256, file_count, byte_size}`.

## Verifikasi signature (wajib di receiver Anda)

```
X-Galardo-Signature: sha256=HMAC_SHA256(secret, raw_body).hexdigest()
```

Python receiver:
```python
import hmac, hashlib
expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
assert hmac.compare_digest(header["X-Galardo-Signature"], f"sha256={expected}")
```
`raw_body` = byte persis yang diterima (jangan re-serialize JSON sebelum verify).

## Perilaku delivery

- Async background thread — hook gagal TIDAK PERNAH memblokir state machine
- Retry: 3 percobaan (backoff 1,5s/3s) untuk 5xx/network; **4xx tidak di-retry**
- Timeout per attempt 8s; delivery log append-only (payload_sha256 tersimpan)
- SSRF guard: cloud metadata endpoints (169.254.0.0/16, dst.) ditolak saat register

## Contoh register

```bash
curl -X POST http://127.0.0.1:8090/api/v1/webhooks \
  -H "Content-Type: application/json" \
  -d '{"name":"grafana","url":"https://monitoring.internal/galardo",
       "secret":"whsec-…","events":["job.completed","job.aborted","evidence.created"]}'
```

## Terbukti E2E (2026-10-10)

Receiver lokal dengan verifikasi HMAC: `hook.ping`, `job.completed`,
`evidence.created` — **semua signature VALID**, delivery attempt 1, status 200.

---

## Status implementasi (2026-10-15)

Event `job.recovery` dan `safety.abort` kini **benar-benar ditembakkan** (sebelumnya
hanya terdaftar di `EVENT_TYPES`):

- `job.recovery` — saat job masuk `RECOVERY_WAIT` (orchestrator `_set_state`).
- `safety.abort` — saat safety controller memicu abort (`abort_fn`), membawa
  `reason_code`, `detail`, `correlation_id`.
- `job.failed` juga dikirim saat `RECOVERY_FAILED`.
