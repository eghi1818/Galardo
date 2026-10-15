#!/usr/bin/env python3
"""GALARDO - uji live T3 Cloudflare edge override, ujung ke ujung.

Hanya butuh GALARDO_CF_TOKEN + GALARDO_CF_ZONE_NAME.
Zone ID dan Account ID ditemukan otomatis dari token.
"""
import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

import envload  # noqa: E402
envload.load()

import routeoverride as ro  # noqa: E402


def mask(v):
    if not v:
        return "-"
    return (v[:6] + "..." + v[-4:]) if len(v) > 12 else (v[:4] + "...")


def wait_dns(host, tries=12, delay=3.0):
    """Host harus resolve sebelum diuji; flush cache DNS macOS kalau perlu."""
    for i in range(tries):
        try:
            socket.getaddrinfo(host, 443)
            return True, i + 1
        except Exception:
            subprocess.run(["dscacheutil", "-flushcache"], capture_output=True)
            time.sleep(delay)
    return False, tries


def main():
    c = ro.CloudflareClient()
    if not c.token:
        print("GALARDO_CF_TOKEN kosong")
        print("T3_TANPA_ENV")
        return 2
    print("token    :", mask(c.token), "(%d karakter)" % len(c.token))

    v = c.verify_token()
    print("token cek: ok=%s HTTP=%s" % (v.get("_ok"), v.get("_http_status")))
    if not v.get("_ok"):
        print("  errors:", json.dumps(v.get("errors"))[:240])
        print("T3_TOKEN_GAGAL")
        return 3

    d = c.discover()
    print("discover : ok=%s zone=%s account=%s"
          % (d.get("ok"), d.get("zone_name"), mask(d.get("account_id"))))
    if d.get("zones"):
        print("  zone terlihat token:", ", ".join(str(z) for z in d["zones"][:10]))
    if d.get("errors"):
        print("  catatan:", "; ".join(d["errors"]))
    if not d.get("ok"):
        print("T3_DISCOVERY_GAGAL")
        return 4

    zi = c.zone_info()
    print("zone     : %s | status=%s | paused=%s | plan=%s"
          % (zi.get("name"), zi.get("status"), zi.get("paused"), zi.get("plan")))
    if zi.get("status") != "active":
        print("  PERINGATAN: zone belum active -> edge belum melayani")
        for ns in (zi.get("name_servers") or []):
            print("    NS:", ns)

    zone = c.zone_name()
    host = os.environ.get("GALARDO_CF_TEST_HOST") or ("galardo-edge." + zone)
    print("host uji :", host)

    if zi.get("status") == "active":
        c.ensure_proxied_host(host)
        okdns, tries = wait_dns(host)
        print("dns host :", "resolve OK" if okdns else "TIDAK RESOLVE",
              "(percobaan %d)" % tries)
        if not okdns:
            print("  -> host belum bisa di-resolve; T3 akan gagal walau API sukses")

    report = {"zone": zone, "host": host, "zone_status": zi.get("status"), "steps": []}
    ok_all = True
    for mode, paths in (("404", ["/blocked/*"]), ("blank", ["/*"])):
        print("\n=== mode %s  paths=%s ===" % (mode, paths))
        spec = ro.OverrideSpec(host, paths=paths, mode=mode, label="t3-check")
        t3 = ro.CloudflareEdgeOverride(client=c, host=host)
        res = t3.apply(spec)
        a = res.artifact or {}
        print("  ok         :", res.ok)
        print("  detail     :", res.detail)
        print("  dns        : ok=%s status=%s"
              % ((a.get("steps") or {}).get("dns", {}).get("ok"), a.get("dns_status")))
        print("  upload     : mode=%s HTTP=%s" % (a.get("upload_mode"), a.get("upload_status")))
        print("  route      : HTTP=%s id=%s" % (a.get("route_status"), a.get("route_id")))
        print("  probe edge :", json.dumps(a.get("probe")))
        report["steps"].append({
            "mode": mode, "ok": bool(res.ok), "detail": res.detail,
            "upload_mode": a.get("upload_mode"), "upload_status": a.get("upload_status"),
            "route_status": a.get("route_status"), "route_id": a.get("route_id"),
            "dns_status": a.get("dns_status"), "probe": a.get("probe")})
        if not res.ok:
            ok_all = False
        rv = t3.revert(spec.spec_id)
        print("  revert     : ok=%s %s" % (rv.ok, rv.detail))

    report["ok"] = ok_all
    report["api_calls"] = c.calls[-30:]
    print("\n" + "-" * 62)
    print(json.dumps(report, indent=2, default=str)[:2200])
    print("-" * 62)
    print("T3_OK" if ok_all else "T3_TIDAK_OK")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
