"""GALARDO - pembaca .env minimal (100% stdlib).

Dipakai supaya nilai di .env terbaca sama seperti variabel shell.
Tidak menimpa variabel yang sudah ada di environment kecuali override=True.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        if k:
            out[k] = v
    return out


def load(path=None, override=False):
    path = path or os.environ.get("GALARDO_ENV", os.path.join(ROOT, ".env"))
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as fh:
            data = parse(fh.read())
    except Exception:
        return {}
    for k, v in data.items():
        if override or k not in os.environ:
            os.environ[k] = v
    return data


def status():
    keys = ("GALARDO_CF_TOKEN", "GALARDO_CF_ACCOUNT_ID", "GALARDO_CF_ZONE_ID",
            "GALARDO_CF_TEST_HOST", "GALARDO_DEV_TOKEN", "GALARDO_API_PORT")
    return {k: ("set" if os.environ.get(k) else "kosong") for k in keys}
