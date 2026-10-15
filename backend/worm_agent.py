#!/usr/bin/env python3
"""GALARDO - satu simpul worm.

Mematuhi LEASE. Kalau lease-nya tidak diperbarui (induk mati / jaringan putus),
simpul ini bunuh diri beserta seluruh anaknya. Itu artinya FAIL-CLOSED:
tidak ada proses yatim yang terus membebani target.

Lease hilang juga dianggap mati (fail-closed), bukan dianggap hidup.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time


def read_lease(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def write_lease(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


class Agent:
    def __init__(self, a):
        self.id = a.id
        self.lease = a.lease
        self.ttl = float(a.ttl)
        self.grace = float(a.grace)
        self.depth = int(a.depth)
        self.max_depth = int(a.max_depth)
        self.children_n = int(a.children)
        self.children = []
        self.running = True
        self.started = time.time()

    def spawn_children(self):
        if self.depth >= self.max_depth:
            return
        d = os.path.dirname(self.lease) or "."
        for i in range(self.children_n):
            cid = "%s.%d" % (self.id, i)
            cpath = os.path.join(d, "lease-%s.json" % cid)
            write_lease(cpath, {"agent_id": cid, "expires_at": time.time() + self.ttl,
                                "parent": self.id, "depth": self.depth + 1})
            try:
                p = subprocess.Popen(
                    [sys.executable, os.path.abspath(__file__),
                     "--id", cid, "--lease", cpath, "--ttl", str(self.ttl),
                     "--grace", str(self.grace), "--depth", str(self.depth + 1),
                     "--max-depth", str(self.max_depth), "--children", str(self.children_n)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.children.append({"id": cid, "lease": cpath, "proc": p})
            except Exception as e:
                print("[agent %s] gagal lahir %s: %s" % (self.id, cid, e))

    def renew_children(self, now):
        for c in self.children:
            write_lease(c["lease"], {"agent_id": c["id"], "expires_at": now + self.ttl,
                                     "parent": self.id, "depth": self.depth + 1})

    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: self.die("SIGTERM"))
        self.spawn_children()
        print("[agent %s] hidup depth=%d anak=%d pid=%d"
              % (self.id, self.depth, len(self.children), os.getpid()))
        while self.running:
            now = time.time()
            l = read_lease(self.lease)
            if l is None:
                if now - self.started > self.ttl + self.grace + 2.0:
                    self.die("lease HILANG > %.1fs (fail-closed)" % (self.ttl + self.grace))
                    break
            else:
                exp = float(l.get("expires_at") or 0)
                if now > exp + self.grace:
                    self.die("lease BASI %.2fs (fail-closed)" % (now - exp))
                    break
                self.renew_children(now)
            time.sleep(0.4)
        self.die("selesai")

    def die(self, reason):
        print("[agent %s] MATI: %s" % (self.id, reason))
        for c in self.children:
            try:
                c["proc"].terminate()
            except Exception:
                pass
        for c in self.children:
            try:
                c["proc"].wait(timeout=3)
            except Exception:
                try:
                    c["proc"].kill()
                except Exception:
                    pass
        sys.exit(0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--lease", required=True)
    ap.add_argument("--ttl", type=float, default=4.0)
    ap.add_argument("--grace", type=float, default=3.0)
    ap.add_argument("--depth", type=int, default=0)
    ap.add_argument("--max-depth", type=int, default=2)
    ap.add_argument("--children", type=int, default=2)
    Agent(ap.parse_args()).run()
