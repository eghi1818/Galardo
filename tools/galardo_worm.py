#!/usr/bin/env python3
"""GALARDO - demo worm: replikasi bercabang, lalu buktikan cascade fail-closed."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

import worm  # noqa: E402

TTL = float(os.environ.get("GALARDO_WORM_TTL", "3"))
GRACE = float(os.environ.get("GALARDO_WORM_GRACE", "2"))


def main():
    t = worm.WormTree(roots=2, children=2, max_depth=2, ttl=TTL, grace=GRACE)
    print("run      :", t.run_id)
    print("topologi : %d akar x %d anak, kedalaman %d -> %d proses"
          % (t.roots, t.children, t.max_depth, t.expected_agents()))
    print("ttl/grace: %.1fs / %.1fs" % (TTL, GRACE))
    print("-" * 62)

    t.build()
    time.sleep(2.5)
    st = t.status()
    print("SETELAH LAHIR : akar hidup=%s | lease tercatat=%d"
          % (st["roots_alive"], len(st["leases"])))
    for l in st["leases"]:
        print("   lease: %-12s depth=%s induk=%s" % (l.get("agent_id"), l.get("depth"), l.get("parent")))

    print("-" * 62)
    print("SIMPUL KORDINATOR MATI (berhenti memperbarui lease) ...")
    t0 = time.time()
    t.stop_renew()
    dead = t.wait_all_dead(timeout=TTL + GRACE + 12)
    print("SEMUA AKAR MATI dalam %.1fs: %s" % (time.time() - t0, dead))
    print("proses yatim tersisa: %s" % (t.alive() or "tidak ada"))

    print("-" * 62)
    print("BUKTI FAIL-CLOSED: akar mati TANPA dikirim sinyal (hanya lease basi).")
    print("Anak-anaknya ikut mati karena lease mereka juga basi -> cascade.")
    sisa = t.reap()
    print("sisa proses yang perlu dibersihkan manual:", sisa)
    t.cleanup()
    print("-" * 62)
    print(json.dumps({"all_dead": dead, "ttl": TTL, "grace": GRACE,
                      "expected_agents": t.roots + t.roots * t.children}, indent=2))
    print("WORM_OK" if dead else "WORM_GAGAL")
    return 0 if dead else 1


if __name__ == "__main__":
    sys.exit(main())
