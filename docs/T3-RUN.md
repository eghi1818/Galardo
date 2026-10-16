# Catatan Uji T3 Live (koler.space) — STEP-48

Harness: `make t3` -> `tools/galardo_t3_check.py`.
Tujuan: buktikan paksa 404/blank lewat edge Cloudflare nyata (bukan target lab).

## Output

```
python3 tools/galardo_t3_check.py
token    : cfut_0...16c1 (53 karakter)
token cek: ok=True HTTP=200
discover : ok=True zone=koler.space account=f11cc3...4af2
  zone terlihat token: koler.space
zone     : koler.space | status=active | paused=False | plan=Free Website
host uji : galardo-edge.koler.space
dns record: True | record sudah proxied
dns host : resolve OK (percobaan 1)

=== mode 404  paths=['/blocked/*'] ===
  ok         : True
  detail     : edge LIVE: https://galardo-edge.koler.space/blocked -> 404 + X-Galardo-Override:404 (2 attempt)
  dns        : ok=True status=None
  upload     : mode=service-worker HTTP=200
  route      : HTTP=200 id=2fd65d81f8de4efbabe783e860572da6
  probe edge : {"status": 404, "header": "404", "body_len": 18, "latency_ms": 148.1, "url": "https://galardo-edge.koler.space/blocked?__gb=ba749308b1a3a46e", "attempts": 2}
  revert     : ok=True T3 reverted: {"route_deleted": true, "worker_deleted": true, "dns_kept": true}

=== mode blank  paths=['/*'] ===
  ok         : True
  detail     : edge LIVE: https://galardo-edge.koler.space/ -> 200 + X-Galardo-Override:blank (2 attempt)
  dns        : ok=True status=None
  upload     : mode=service-worker HTTP=200
  route      : HTTP=200 id=bc32eaf23153472fbedf08e820ac2ecc
  probe edge : {"status": 200, "header": "blank", "body_len": 0, "latency_ms": 298.3, "url": "https://galardo-edge.koler.space/?__gb=4808934eb18d97c8", "attempts": 2}
  revert     : ok=True T3 reverted: {"route_deleted": true, "worker_deleted": true, "dns_kept": true}

--------------------------------------------------------------
{
  "zone": "koler.space",
  "host": "galardo-edge.koler.space",
  "zone_status": "active",
  "steps": [
    {
      "mode": "404",
      "ok": true,
      "detail": "edge LIVE: https://galardo-edge.koler.space/blocked -> 404 + X-Galardo-Override:404 (2 attempt)",
      "upload_mode": "service-worker",
      "upload_status": 200,
      "route_status": 200,
      "route_id": "2fd65d81f8de4efbabe783e860572da6",
      "dns_status": null,
      "probe": {
        "status": 404,
        "header": "404",
        "body_len": 18,
        "latency_ms": 148.1,
        "url": "https://galardo-edge.koler.space/blocked?__gb=ba749308b1a3a46e",
        "attempts": 2
      }
    },
    {
      "mode": "blank",
      "ok": true,
      "detail": "edge LIVE: https://galardo-edge.koler.space/ -> 200 + X-Galardo-Override:blank (2 attempt)",
      "upload_mode": "service-worker",
      "upload_status": 200,
      "route_status": 200,
      "route_id": "bc32eaf23153472fbedf08e820ac2ecc",
      "dns_status": null,
      "probe": {
        "status": 200,
        "header": "blank",
        "body_len": 0,
        "latency_ms": 298.3,
        "url": "https://galardo-edge.koler.space/?__gb=4808934eb18d97c8",
        "attempts": 2
      }
    }
  ],
  "ok": true,
  "api_calls": [
    {
      "method": "GET",
      "path": "/user/tokens/verify",
      "status": 200,
      "ok": true,
      "errors": []
    },
    {
      "method": "GET",
      "path": "/zones?per_page=50",
      "status": 200,
      "ok": true,
      "errors": []
    },
    {
      "method": "GET",
      "path": "/zones/955743bd6a735db06701aa7f25932729",
      "status": 200,
      "ok": true,
      "errors": []
    },
    {
      "method": "GET",
      "path": "/zones/955743bd6a735db06701aa7f25932729",
      "status": 200,
      "ok": true,
      "errors": []
    },
    {
      "method": "GET",
      "path": "/zones/955743bd6a735db06701aa7f25932729/dns_records?name=galardo-edge.koler.space",
      "status": 200,
      "ok": true,
      "errors": []
    },
    {
      "method": "GET",
      "path": "/zones/955743bd6a735db06701aa7f25932729/dns_records?name=galardo-edge.koler.space",
      "status": 200,
      "ok": true,
      
--------------------------------------------------------------
T3_OK

```
