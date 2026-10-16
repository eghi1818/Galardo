#!/usr/bin/env python3
"""Verifikasi token Cloudflare: validitas, zone, permission, uji tulis DNS.

Pakai:  python3 tools/cf_check.py [--write]
--write  buat TXT uji di zone pertama, baca balik, lalu hapus (uji DNS:Edit).
"""
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.cloudflare.com/client/v4"
WRITE = "--write" in sys.argv
OK = True

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
try:
    import netssl
except Exception:
    netssl = None


def _ctx():
    return netssl.context() if netssl else None


def call(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bearer %s" % token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25, context=_ctx()) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def doh_txt(name):
    """Baca TXT lewat DNS-over-HTTPS 1.1.1.1 (stdlib). None kalau gagal."""
    q = urllib.parse.urlencode({"name": name, "type": "TXT"})
    req = urllib.request.Request("https://cloudflare-dns.com/dns-query?" + q,
                                 headers={"Accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=10, context=_ctx()) as r:
            ans = json.loads(r.read() or b"{}").get("Answer") or []
            return [a.get("data", "").strip('"') for a in ans if a.get("type") == 16]
    except Exception:
        return None


token = (os.environ.get("GALARDO_CF_TOKEN")
         or os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
if not token:
    print("GALARDO_CF_TOKEN KOSONG"); sys.exit(2)

print("token  : %s...%s (%d karakter)" % (token[:8], token[-4:], len(token)))
st, body = call("GET", "/user/tokens/verify", token)
print("verify : http=%s success=%s" % (st, body.get("success")))
if st != 200 or not body.get("success"):
    print("  errors:", json.dumps(body.get("errors") or body, ensure_ascii=False)[:400])
    sys.exit(1)
print("  status token: %s" % (body.get("result") or {}).get("status"))
print()

st, body = call("GET", "/zones?per_page=50", token)
zones = body.get("result") or []
print("zones  : http=%s jumlah=%d" % (st, len(zones)))
for z in zones:
    print("  - %-20s status=%-8s id=%s" % (z.get("name"), z.get("status"), z.get("id")))
    print("    name_servers: %s" % ", ".join(z.get("name_servers") or [])[:90])
if not zones:
    print("  errors:", json.dumps(body.get("errors") or [], ensure_ascii=False)[:300])
    OK = False
active = [z for z in zones if z.get("status") == "active"]
print("  zone ACTIVE: %d" % len(active))
print()

st, body = call("GET", "/accounts?per_page=50", token)
accs = body.get("result") or []
print("accounts: http=%s jumlah=%d" % (st, len(accs)))
for a in accs:
    print("  - %s id=%s" % (a.get("name"), a.get("id")))
if accs:
    st, body = call("GET", "/accounts/%s/workers/scripts" % accs[0]["id"], token)
    print("workers scripts: http=%s jumlah=%d" % (st, len(body.get("result") or [])))
    if st != 200:
        print("  -> Workers Scripts:Edit belum jalan")
        OK = False
print()

if WRITE and zones:
    z = zones[0]
    print("=== UJI TULIS DNS di %s ===" % z.get("name"))
    name = "_galardo-check.%s" % z.get("name")
    val = "galardo-check=%s" % secrets.token_hex(8)
    st, body = call("POST", "/zones/%s/dns_records" % z["id"], token,
                    {"type": "TXT", "name": name, "content": val, "ttl": 60})
    rec = body.get("result") or {}
    print("  buat TXT : http=%s success=%s id=%s" % (st, body.get("success"), rec.get("id")))
    if st not in (200, 201):
        print("  errors:", json.dumps(body.get("errors") or [], ensure_ascii=False)[:300])
        print("  -> DNS:Edit BELUM jalan")
        OK = False
    else:
        st2, body2 = call("GET", "/zones/%s/dns_records/%s" % (z["id"], rec["id"]), token)
        got = (body2.get("result") or {}).get("content")
        print("  baca balik: http=%s cocok=%s" % (st2, got == val))
        live = doh_txt(name)
        if live is None:
            print("  resolusi publik: TIDAK BISA DIBACA (jaringan/DNS)")
        elif any(val in x for x in live):
            print("  resolusi publik: OK -> zone ACTIVE, TXT live")
        else:
            print("  resolusi publik: BELUM TERLIHAT -> zone kemungkinan masih PENDING")
            print("    (record dibuat di Cloudflare, tapi NS belum diarahkan ke CF)")
        st3, _ = call("DELETE", "/zones/%s/dns_records/%s" % (z["id"], rec["id"]), token)
        print("  hapus TXT: http=%s" % st3)
    print()

print("=== KESIMPULAN ===")
if not active:
    print("  T3 BELUM BERFUNGSI: tidak ada zone berstatus active.")
    print("  -> arahkan nameserver koler.space ke Cloudflare, tunggu status 'active'.")
else:
    print("  T3 bisa diuji di: %s" % ", ".join(z.get("name") for z in active))
print("  Target pihak ketiga (zone bukan milik kita) -> hanya T1/T2 yang berlaku.")
print("  Rung 1 kepemilikan (TXT DNS) %s." % ("BISA dipakai" if OK else "belum bisa dipakai"))
sys.exit(0 if OK else 1)
