#!/usr/bin/env python3
"""P1.4 / STEP-55 - bukti end-to-end rung dns_txt (rank 4) kepemilikan domain.

Rantai: ownership.Challenge -> TXT lewat Cloudflare API -> netdns.txt_quorum (2/3)
        -> ownership.Proof.ok -> adapt_dns_proof (rank 4) -> gate(min_level=dns_txt)

Mode: --dry-run (tanpa jaringan, default) | --live (tulis TXT nyata, lalu bersihkan)
Exit: 0 OWN1_OK | 1 OWN1_TIDAK_OK | 2 prasyarat gagal (TANPA_ENV / ZONE_SALAH)
Stdlib only. Python 3.9 compatible.
"""
from __future__ import annotations

import argparse, json, os, subprocess, sys, time
import urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import netdns
import netssl
import ownership
import ownership_ladder as ol

API = "https://api.cloudflare.com/client/v4"
DOMAIN = "koler.space"
OUT = os.path.join(ROOT, ".out", "HASIL-55.md")
LABEL = ownership.PRIMARY_LABEL
LOG, PASS, FAIL = [], 0, 0


def log(line=""):
    print(line)
    LOG.append(str(line))


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        log("  ok   %s" % name)
    else:
        FAIL += 1
        log("  FAIL %s   <-- %r" % (name, detail))


def mask(token):
    return "%s...%s (%d)" % (token[:8], token[-4:], len(token)) if token else "-"


def head_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "-"


def load_env(path=None):
    try:
        with open(path or os.path.join(ROOT, ".env"), "r") as fh:
            raw = fh.readlines()
    except OSError:
        return
    for line in raw:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip():
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cf(method, path, token, body=None, timeout=25):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": "Bearer %s" % token,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=netssl.context()) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"{}")
        except Exception:
            return exc.code, {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def discover_zone(token, domain):
    st, body = cf("GET", "/zones?per_page=50", token)
    log("  GET /zones http=%s jumlah=%s" % (st, len(body.get("result") or [])))
    for z in (body.get("result") or []):
        if str(z.get("name", "")).lower() == domain.lower():
            return z
    return None


def txt_records(token, zone_id, name):
    q = urllib.parse.urlencode({"type": "TXT", "name": name, "per_page": 100})
    return cf("GET", "/zones/%s/dns_records?%s" % (zone_id, q), token)


def put_txt(token, zone_id, name, value, ttl=60):
    return cf("POST", "/zones/%s/dns_records" % zone_id, token,
              {"type": "TXT", "name": name, "content": value, "ttl": ttl})


def del_txt(token, zone_id, rid):
    return cf("DELETE", "/zones/%s/dns_records/%s" % (zone_id, rid), token)


def chain(proof, domain, account):
    lp = ol.adapt_dns_proof(proof, domain, account)
    return lp, ol.OwnershipLadder(min_level="dns_txt").gate(lp)


def dry_run():
    log("== DRY-RUN: rantai kelas tanpa jaringan ==")
    ch = ownership.Challenge(DOMAIN, "usr-verify", label=LABEL)
    log("  record_name : %s" % ch.record_name)
    check("record_name = label + domain",
          ch.record_name == "%s.%s" % (LABEL, DOMAIN), ch.record_name)
    check("expected_value membawa token",
          ch.token in ch.expected_value and ch.expected_value.startswith("galardo-verify="),
          ch.expected_value)
    good = ownership.Proof(True, ch, label=LABEL, record=ch.record_name,
                           evidence={"quorum": "2/3"})
    lp, (g_ok, why) = chain(good, DOMAIN, "usr-verify")
    check("adapt -> rank 4", lp.rank == 4, lp.to_dict())
    check("adapt -> method dns_txt", lp.method == "dns_txt", lp.method)
    check("LadderProof dianggap bukti nyata", lp.is_proof is True, lp.to_dict())
    check("gate lolos pada proof ok", g_ok is True, why)
    bad = ownership.Proof(False, ch, evidence={"attempts": {"_galardo": "kosong"}})
    lp_b, (g_b, why_b) = chain(bad, DOMAIN, "usr-verify")
    check("gate menolak saat proof gagal", g_b is False, why_b)
    check("ladder_proof gagal ikut gagal", lp_b.ok is False, lp_b.to_dict())
    g_a, why_a = ol.OwnershipLadder(min_level="dns_txt").gate(
        ol.attest(DOMAIN, "usr-verify"))
    check("attestasi (rank 1) tidak cukup untuk dns_txt", g_a is False, why_a)
    log()
    log("  DRY-RUN: %d passed, %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


def write_out(path, d):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        pass
    lines = [
        "# HASIL-55 - P1.4 bukti e2e rung dns_txt (rank 4)", "",
        "- Waktu (UTC) : %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "- HEAD        : %s" % head_sha(),
        "- Verdict     : %s" % d["verdict"],
        "- Domain      : %s" % d["domain"],
        "- Zone id     : %s" % d["zone_id"],
        "- Record TXT  : %s" % d["record"],
        "- Nilai       : %s" % d["value"],
        "- TXT pra-ada : %s" % d["pre"],
        "- Percobaan   : %s" % d["tries"],
        "- proof.ok    : %s" % d["proof"].get("ok"),
        "- ladder      : method=%s rank=%s is_proof=%s"
        % (d["ladder"].get("method"), d["ladder"].get("rank"),
           d["ladder"].get("is_proof")),
        "- gate        : %s (%s)" % (d["gate_ok"], d["gate_why"]),
        "- cleanup     : %s" % d["cleanup"], "",
        "## proof.evidence", "```json",
        json.dumps(d["proof"].get("evidence"), indent=1, ensure_ascii=False)[:4000],
        "```", "", "## log", "```"] + LOG + ["```", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    log("  bukti ditulis: %s" % path)


def live(domain, tries, timeout, keep, out_path):
    log("== LIVE: rung dns_txt di %s ==" % domain)
    load_env()
    token = (os.environ.get("GALARDO_CF_TOKEN")
             or os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
    if not token:
        log("  token KOSONG -> OWN1_TANPA_ENV")
        return 2
    log("  token : %s" % mask(token))
    log("  quorum: %s (butuh 2 dari 3)" % ", ".join(netdns.DEFAULT_RESOLVERS))

    zone = discover_zone(token, domain)
    if zone is None or str(zone.get("status")) != "active":
        log("  zona tidak ada / tidak ACTIVE -> OWN1_ZONE_SALAH")
        return 2
    zid = zone.get("id")
    log("  zone  : %s status=%s id=%s" % (zone.get("name"), zone.get("status"), zid))

    ch = ownership.Challenge(domain, "usr-verify", label=LABEL)
    name, value = ch.record_name, ch.expected_value
    log("  TXT   : %s = %s" % (name, value))

    st, body = txt_records(token, zid, name)
    pre = len(body.get("result") or []) if st == 200 else -1
    log("  TXT pra-ada: %s" % pre)

    st, body = put_txt(token, zid, name, value)
    if st not in (200, 201) or not body.get("success"):
        log("  POST gagal http=%s errors=%s"
            % (st, json.dumps(body.get("errors") or body)[:300]))
        return 1
    rid = (body.get("result") or {}).get("id")
    log("  POST ok record_id=%s" % rid)

    verifier = ownership.OwnershipVerifier(required=2, timeout=timeout)
    proof = None
    for attempt in range(1, tries + 1):
        proof = verifier.verify(ch)
        log("  resolusi %d/%d -> ok=%s evidence=%s"
            % (attempt, tries, proof.ok, json.dumps(proof.evidence)[:200]))
        if proof.ok:
            break
        time.sleep(min(0.5 * (2 ** attempt), 8.0))

    lp, (g_ok, why) = chain(proof, domain, "usr-verify")
    log("  LadderProof: method=%s rank=%s is_proof=%s" % (lp.method, lp.rank, lp.is_proof))
    log("  gate: %s (%s)" % (g_ok, why))

    cleanup = "dilewati (--keep)"
    if not keep and rid:
        st, body = del_txt(token, zid, rid)
        cleanup = "http=%s success=%s" % (st, body.get("success"))
        log("  cleanup: %s" % cleanup)

    verdict = "OWN1_OK" if (proof.ok and g_ok) else "OWN1_TIDAK_OK"
    write_out(out_path, dict(verdict=verdict, domain=domain, zone_id=zid, record=name,
                             value=value, tries=tries, proof=proof.to_dict(),
                             ladder=lp.to_dict(), gate_ok=g_ok, gate_why=why,
                             cleanup=cleanup, pre=pre))
    log()
    log("  VERDICT: %s" % verdict)
    return 0 if verdict == "OWN1_OK" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="P1.4 bukti e2e rung dns_txt (rank 4)")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--domain", default=DOMAIN)
    ap.add_argument("--tries", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=6.0)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    if a.live and a.dry_run:
        print("pilih salah satu: --live atau --dry-run")
        return 2
    if a.live:
        return live(a.domain, a.tries, a.timeout, a.keep, a.out)
    return dry_run()


if __name__ == "__main__":
    sys.exit(main())
