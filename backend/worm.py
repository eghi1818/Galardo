"""GALARDO - koordinator worm: replikasi bercabang + terminasi fail-closed.

Modelnya sederhana dan jujur:

    koordinator
      +-- akar-0
      |     +-- akar-0.0
      |     +-- akar-0.1
      +-- akar-1
            +-- akar-1.0
            +-- akar-1.1

Koordinator menulis lease setiap akar. Setiap akar menulis lease anaknya.
Kalau koordinator berhenti memperbarui lease (mati / putus jaringan), akar
mati setelah ttl+grace, lalu anak-anaknya mati karena lease mereka juga basi.
Cascade. Tidak ada proses yatim.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, "worm_agent.py")
DEFAULT_DIR = os.path.join(os.path.dirname(HERE), ".galardo", "worm")


class WormTree:
    def __init__(self, run_id=None, root_dir=None, roots=2, children=2, max_depth=2,
                 ttl=4.0, grace=3.0, renew_interval=0.5):
        self.run_id = run_id or ("run-%d" % int(time.time()))
        self.dir = os.path.join(root_dir or DEFAULT_DIR, self.run_id)
        self.roots = int(roots)
        self.children = int(children)
        self.max_depth = int(max_depth)
        self.ttl = float(ttl)
        self.grace = float(grace)
        self.renew_interval = float(renew_interval)
        self.procs = []
        self.renewing = False
        self._t = None

    # ---------------- lease ----------------
    def _root_lease(self, i):
        return os.path.join(self.dir, "lease-root-%d.json" % i)

    def _write(self, path, data):
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)

    def renew_once(self):
        now = time.time()
        for i in range(self.roots):
            self._write(self._root_lease(i), {"agent_id": "root-%d" % i,
                                              "expires_at": now + self.ttl,
                                              "parent": "coordinator", "depth": 0})

    def _renew_loop(self):
        while self.renewing:
            try:
                self.renew_once()
            except Exception:
                pass
            time.sleep(self.renew_interval)

    # ---------------- lifecycle ----------------
    def build(self):
        os.makedirs(self.dir, exist_ok=True)
        self.renew_once()
        for i in range(self.roots):
            p = subprocess.Popen(
                [sys.executable, AGENT, "--id", "root-%d" % i,
                 "--lease", self._root_lease(i), "--ttl", str(self.ttl),
                 "--grace", str(self.grace), "--depth", "0",
                 "--max-depth", str(self.max_depth), "--children", str(self.children)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.procs.append({"id": "root-%d" % i, "proc": p})
        self.renewing = True
        self._t = threading.Thread(target=self._renew_loop, daemon=True, name="worm-renew")
        self._t.start()
        return self

    def stop_renew(self):
        """Simulasi koordinator mati: berhenti memperbarui lease."""
        self.renewing = False
        if self._t:
            self._t.join(timeout=2)

    def resume_renew(self):
        if not self.renewing:
            self.renewing = True
            self._t = threading.Thread(target=self._renew_loop, daemon=True)
            self._t.start()

    def expected_agents(self):
        return sum(self.roots * (self.children ** d) for d in range(self.max_depth + 1))

    def alive(self):
        out = []
        for r in self.procs:
            if r["proc"].poll() is None:
                out.append(r["id"])
        return out

    def status(self):
        leases = []
        if os.path.isdir(self.dir):
            for f in sorted(os.listdir(self.dir)):
                if f.startswith("lease-") and f.endswith(".json"):
                    try:
                        with open(os.path.join(self.dir, f)) as fh:
                            leases.append(json.load(fh))
                    except Exception:
                        pass
        return {"run_id": self.run_id, "dir": self.dir, "ttl": self.ttl, "grace": self.grace,
                "roots": self.roots, "children": self.children, "max_depth": self.max_depth,
                "expected_agents": self.expected_agents(),
                "roots_alive": self.alive(), "renewing": self.renewing,
                "leases": leases}

    def wait_all_dead(self, timeout=30.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.alive():
                return True
            time.sleep(0.4)
        return False

    def stop(self):
        self.stop_renew()
        for r in self.procs:
            try:
                r["proc"].terminate()
            except Exception:
                pass
        for r in self.procs:
            try:
                r["proc"].wait(timeout=3)
            except Exception:
                try:
                    r["proc"].kill()
                except Exception:
                    pass

    def reap(self):
        """Bunuh sisa proses agent (kalau koordinator crash keras)."""
        killed = 0
        try:
            p = subprocess.run(["pgrep", "-f", "worm_agent.py"], capture_output=True, text=True)
            for pid in (p.stdout or "").split():
                try:
                    os.kill(int(pid), 15)
                    killed += 1
                except Exception:
                    pass
        except Exception:
            pass
        return killed

    def cleanup(self):
        self.stop()
        shutil.rmtree(self.dir, ignore_errors=True)
