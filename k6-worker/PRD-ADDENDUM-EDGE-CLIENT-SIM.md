# PRD ADDENDUM — Edge Client Simulation (direct-to-origin, identity-synthetic)
**Status:** APPROVED scope (user, 2026-10-09) · **Parent doc:** 01_Galardo_PRD.md v1.0
**Schema:** scenario schema **v1.1** (`identity_sim` block) · **Modul:** `backend/identity_sim.py`, `k6-worker/scenario_k6.js`

---

## 1. Tujuan

Menguji ketahanan **modul internal** origin milik sendiri di bawah tekanan ribuan
identitas klien heterogen:

| Target modul | Metrik |
|---|---|
| Parsing `CF-Connecting-IP` / `X-Forwarded-For` | akurasi ekstraksi vs pool identitas |
| LB hashing algorithm | distribusi request → hash bucket (kurva + entropy) |
| Session table | saturasi pada churn `per-iteration` vs sticky `per-vu` |
| Socket allocation | kegagalan alokasi, ephemeral port pressure (connection churn) |
| TTFB distribusi | p50/p95/p99 per bucket identitas |

## 2. Definisi identitas (synthetic identity)

- Identitas = **header-level value**: `CF-Connecting-IP` / `X-Forwarded-For` /
  `X-Client-Id` + `X-Session-Id` + User-Agent bervariasi.
- **Sumber TCP nyata** tetap IP terdaftar worker VM — tidak ada spoofing paket.
- Pool **deterministik** dari seed (reproduksibel untuk evidence): pool identik
  di-regenerate di worker mana pun via `GET /api/v1/identity-pool?count=&seed=`.
- Pool maksimum **50.000** identitas per skenario; default program 10.000.

## 3. Dua jalur simulasi

| Path | Header carrier | Jalur jaringan | Catatan |
|---|---|---|---|
| `edge` (default) | `X-Client-Id` + `X-Session-Id` | via Cloudflare | edge-safe (terverifikasi: CF 200). Modul origin membaca identitas dari X-Client-Id. |
| `direct` | `CF-Connecting-IP` + `X-Forwarded-For` | direct-to-origin (bypass edge) | HANYA valid jika origin firewall meng-allowlist IP worker. CF edge menolak `CF-Connecting-IP` spoofed dari internet dengan 403 — itu perilaku benar edge, terbukti saat verifikasi. |

Kedua jalur menghasilkan tekanan identik pada modul internal; `direct` memberi
sinyal paling bersih karena tidak melewati edge pooling.

## 4. Batas yang DIKUNCI (legal & arsitektural) — tidak dapat diubah via scenario/AI

1. **Tidak ada proxy pihak ketiga** — residential/commercial proxy, rotasi IP sewaan, IP pool dinamis eksternal: **dilarang** (Prolog §1, PRD §5.2, Blueprint §8 tetap berlaku).
2. **Tidak ada packet-level spoofing** — identitas hanya header value.
3. **Tidak ada tujuan evasi** — pengujian mengukur blocking, bukan menghindarinya. Safety controller tidak boleh dinonaktifkan oleh identity_sim.
4. **Sumber TCP = worker terdaftar** — semua traffic tetap berasal dari fleet beridentitas.
5. AI tidak boleh mengubah blok ini (Governance §1 berlaku penuh).

## 5. Skema scenario v1.1

```yaml
schema_version: "1.1"
name: "wecash-edge-sim"
target_ref: "wecash-ai-prod"
identity_sim:
  enabled: true
  count: 10000        # 1..50000 (policy can cap lower)
  churn: per-iteration # atau per-vu (sticky session)
  path: edge           # edge | direct
  seed: wecash-edge-sim
profile: { ... }        # tidak berubah
requests: [ ... ]       # tidak berubah
```

Validasi server-side: `identity_sim.count` wajib 1..50000, `churn` ∈ {per-iteration,
per-vu}, `path` ∈ {edge, direct}, seed string 4..64. Error field-level sesuai FR.

## 6. Implementasi (terverifikasi 2026-10-09)

- `identity_sim.py`: generator pool deterministik (16 CIDR sintetis × LCG),
  bucket hash SHA-256 (64 bucket), entropy calculation, `pool_meta`.
- `scenario.py`: schema 1.1, blok `identity_sim` masuk normalized JSON + hash.
- `scenario_k6.js`: pool via `GALARDO_ID_POOL_FILE` (menghindari ARG_MAX),
  `per-iteration` churn + no-keep-alive (connection churn), summary membawa
  `identity_sim` metadata.
- API: `GET /api/v1/identity-pool?count&seed` → pool + bucket_counts + entropy.
- Dashboard: Visual Mode — section Identity Simulation (enable toggle, path/churn/
  count/seed); Live Execution — panel distribusi identitas (64-bucket expected curve
  + entropy + path note).

**Verifikasi k6 (10K identitas, edge, 60s @ 50 rps):** 2.999 req @ 48.9 rps,
p50 546 ms / p95 1.59 s, failed 0.67%, pool_size 10000 ✓.

## 7. Out of scope (tetap)

Proxy pool/rotation segala bentuk, residential/commercial IP bridge, spoofing
paket, penyembunyian sumber, bypass rate-limit (lihat §4).
