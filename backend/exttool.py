"""GALARDO - integrasi tool eksternal (fail-open).

Peta tool -> GOAL:
    subfinder   -> BYPASS/origin : enumerasi subdomain -> kandidat origin
    nikto       -> 404 & BLANK   : pemindaian web server -> temuan
    traceroute  -> DOWN          : jejak hop + latensi

Prinsip (sama seperti netssl/pg): biner tak ada, error, atau timeout TIDAK melempar.
Hasil selalu terstruktur dan memuat alasan, supaya Galardo tetap jalan tanpa tool.
"""
import os
import re
import shutil
import subprocess
import time

TIMEOUT_ENV = "GALARDO_EXTTOOL_TIMEOUT"
MAX_OUT = 200000

TOOLS = {
    "subfinder": {"bin": "subfinder", "goal": "bypass",
                  "desc": "enumerasi subdomain (kandidat origin)", "butuh": "network"},
    "nikto": {"bin": "nikto", "goal": "404/blank",
              "desc": "pemindaian web server (temuan 404/blank/header)", "butuh": "network"},
    "traceroute": {"bin": "traceroute", "goal": "down",
                   "desc": "jejak hop + latensi", "butuh": "network"},
}


def timeout_default():
    try:
        return float(os.environ.get(TIMEOUT_ENV) or 20.0)
    except ValueError:
        return 20.0


def status():
    """Status tiap tool: ada/tidak + path. Tidak pernah melempar."""
    out = {}
    for nama, spec in TOOLS.items():
        exe = shutil.which(spec["bin"])
        out[nama] = {"available": bool(exe), "path": exe or "", "goal": spec["goal"],
                     "desc": spec["desc"], "butuh": spec["butuh"]}
    out["_timeout_default"] = timeout_default()
    return out


def tersedia(nama):
    spec = TOOLS.get(nama)
    return bool(spec and shutil.which(spec["bin"]))


# ---------------------------------------------------------------- parser

def parse_traceroute(teks):
    hops = []
    for line in teks.splitlines():
        m = re.match(r"\s*(\d+)\s+(.+)$", line)
        if not m:
            continue
        sisa = m.group(2)
        mh = re.match(r"([A-Za-z0-9._\-]+)\s*\(", sisa)
        rtt = [float(x) for x in re.findall(r"([\d.]+)\s*ms", sisa)]
        hops.append({"hop": int(m.group(1)), "host": mh.group(1) if mh else "", "rtt_ms": rtt})
    return {"hops": hops, "count": len(hops)}


def parse_subfinder(teks):
    sub = []
    for line in teks.splitlines():
        s = line.strip()
        if not s or s.startswith("[") or " " in s:
            continue
        sub.append(s)
    return {"subdomains": sub, "count": len(sub)}


def parse_nikto(teks):
    temuan = [l.strip()[2:].strip() for l in teks.splitlines() if l.strip().startswith("+ ")]
    return {"findings": temuan, "count": len(temuan)}


PARSER = {"traceroute": parse_traceroute, "subfinder": parse_subfinder, "nikto": parse_nikto}


def parse(nama, teks):
    fn = PARSER.get(nama)
    if not fn:
        return {}
    try:
        return fn(teks)
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


# ---------------------------------------------------------------- runner

def run(nama, args=None, timeout=None, target=None):
    """Jalankan tool. Selalu mengembalikan dict; tidak melempar."""
    t0 = time.time()
    spec = TOOLS.get(nama)
    if not spec:
        return {"ok": False, "tool": nama, "reason": "tool tak dikenal",
                "tersedia": sorted(TOOLS.keys())}
    exe = shutil.which(spec["bin"])
    if not exe:
        return {"ok": False, "available": False, "tool": nama, "elapsed": 0.0,
                "reason": "biner '%s' tak ditemukan di PATH" % spec["bin"],
                "goal": spec["goal"]}
    argv = [exe] + [str(a) for a in (args or [])]
    if target and target not in argv:
        argv.append(str(target))
    tmo = float(timeout or timeout_default())
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=tmo)
        out = p.stdout or ""
        if p.stderr:
            out += "\n[stderr]\n" + p.stderr
        potong = len(out) > MAX_OUT
        out = out[:MAX_OUT]
        return {"ok": p.returncode == 0, "available": True, "tool": nama, "argv": argv,
                "rc": p.returncode, "timeout": tmo, "truncated": potong,
                "elapsed": round(time.time() - t0, 2), "goal": spec["goal"],
                "parsed": parse(nama, out), "output": out}
    except subprocess.TimeoutExpired:
        return {"ok": False, "available": True, "tool": nama, "argv": argv, "timeout": tmo,
                "elapsed": round(time.time() - t0, 2), "goal": spec["goal"],
                "reason": "timeout setelah %.1fs" % tmo}
    except Exception as exc:
        return {"ok": False, "available": True, "tool": nama, "argv": argv,
                "elapsed": round(time.time() - t0, 2), "goal": spec["goal"],
                "reason": "%s: %s" % (type(exc).__name__, exc)}
