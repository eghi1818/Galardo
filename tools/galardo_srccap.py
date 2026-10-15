#!/usr/bin/env python3
"""GALARDO - uji registry kapabilitas sumber: probe nyata + pick()."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

import envload  # noqa: E402
envload.load()

import srccap  # noqa: E402

URL = os.environ.get("GALARDO_SRC_PROBE_URL", "https://koler.space/")


def main():
    print("probe target:", URL)
    print("-" * 60)
    s = srccap.ensure_local(URL)
    d = s.to_dict(with_evidence=True)
    print("sumber     :", d["id"], "(%s)" % d["kind"])
    print("proven     :", d["proven"] or "-")
    print("unproven   :", d["unproven"] or "-")
    print("na (lib)   :", d.get("na") or "-")
    print("declared   :", d["declared"] or "-")
    print("kapabilitas:", d["capabilities"] or "-")
    ev = d["evidence"]
    print("lib ssl    :", ev.get("ssl_lib"))
    print("bukti:")
    for k in ("http1", "keepalive", "tls13", "tls12", "ipv6"):
        print("   %-10s %s" % (k, json.dumps(ev.get(k))[:120]))

    print("-" * 60)
    print("uji pick():")
    for need in (["http1", "tls13"], ["http1", "udp"], ["http1", "spoof_src", "residential"]):
        src, why = srccap.REGISTRY.pick(need)
        print("   butuh %-34s -> %s %s"
              % (",".join(need), src.source_id if src else "TIDAK ADA",
                 "" if src else "| " + "; ".join(why)))

    print("-" * 60)
    print(json.dumps(srccap.REGISTRY.matrix(), indent=2)[:1200])
    print("SRCCAP_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
