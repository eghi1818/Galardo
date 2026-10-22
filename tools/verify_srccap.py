#!/usr/bin/env python3
"""Item 9: kunci registry kapabilitas sumber/egress (backend/srccap.py).

Offline penuh - probe_egress di-monkeypatch, store diisolasi lewat GALARDO_SOURCES_PATH.
- A Source: validasi kind, filter declared, semantik can/missing
- B registry: register/get/list/remove, sid unik, round-trip save/load
- C pick: cocok, filter kind, alasan saat kurang, alasan saat registry kosong
- D probe: PROBE_OWNED tidak menghapus cap prober lain; probe_count/ip terurus
- E mark_proven: pindah na/unproven -> proven, evidence tergabung
- F matrix: bentuk & gaps
- G ensure_local idempoten
- H pengunci sumber
Stdlib only. Exit 1 bila ada yang gagal.
"""
import os, sys, tempfile, shutil

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TMP = tempfile.mkdtemp(prefix="galardo-srccap-")
os.environ["GALARDO_SOURCES_PATH"] = os.path.join(TMP, "sources.json")
sys.path.insert(0, os.path.join(ROOT, "backend"))
import srccap as sc  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


print("== A. Source ==")
s = sc.Source("src-a", "A", kind="vps", declared=["udp", "NGAWUR", "spoof_src"])
check("A declared difilter ke CAPABILITIES", s.declared == ["spoof_src", "udp"], s.declared)
check("A capabilities = proven ∪ declared", s.capabilities() == ["spoof_src", "udp"])
s.proven = ["http1"]
check("A can() butuh SEMUA", s.can("http1", "udp") is True and s.can("http1", "ipv6") is False)
check("A missing() menyebut yang kurang", s.missing("http1", "ipv6", "tls13") == ["ipv6", "tls13"],
      s.missing("http1", "ipv6", "tls13"))
try:
    sc.Source("x", "X", kind="ngawur")
    check("A kind ngawur ditolak", False, "tidak melempar")
except sc.SourceError:
    check("A kind ngawur ditolak", True)
check("A kind_is_datacenter hanya vps/worker",
      sc.Source("v", "V", kind="vps").to_dict()["kind_is_datacenter"] is True
      and sc.Source("l", "L", kind="local").to_dict()["kind_is_datacenter"] is False)

print("== B. registry & persistensi ==")
r = sc.SourceRegistry()
r.register("alpha", kind="vps", declared=["http1"])
r.register("beta", kind="residential", declared=["residential", "udp"])
check("B register + list", len(r.list()) == 2)
check("B get() bekerja", r.get("src-alpha") is not None)
try:
    r.register("alpha")
    check("B sid duplikat ditolak", False, "tidak melempar")
except sc.SourceError:
    check("B sid duplikat ditolak", True)
path = os.path.join(TMP, "reg.json")
r.save(path)
r2 = sc.SourceRegistry()
n = r2.load(path)
check("B round-trip save/load", n == 2 and r2.get("src-beta").declared == ["residential", "udp"], n)
check("B remove mengembalikan sumber", r.remove("src-alpha") is not None and r.get("src-alpha") is None)

print("== C. pick ==")
r3 = sc.SourceRegistry()
a = r3.register("kaya", kind="vps", declared=["http1", "keepalive"])
b = r3.register("miskin", kind="vps", declared=["http1"])
got, why = r3.pick(["http1", "keepalive"])
check("C pilih yang bisa semua", got is not None and got.source_id == a.source_id, (got, why))
check("C alasan kosong saat cocok", why == [], why)
got2, why2 = r3.pick(["tls13"])
check("C tak ada yang cocok -> None + alasan", got2 is None and why2 and "kurang" in why2[0], why2)
got3, why3 = r3.pick(["http1"], kind="residential")
check("C filter kind dihormati", got3 is None and "residential" in why3[0], why3)
kosong = sc.SourceRegistry()
got4, why4 = kosong.pick(["http1"])
check("C registry kosong -> alasan jelas", got4 is None and "kosong" in why4[0], why4)
check("C required kosong -> ada yang dipilih", r3.pick([])[0] is not None)

print("== D. probe: cap prober lain tidak terhapus ==")
FAKE = {"url": "x", "at": 0.0, "ssl_lib": "fake",
        "proven": ["http1", "keepalive"], "unproven": ["ipv6"], "na": ["http2", "tls12"],
        "evidence": {"http1": {"ok": True}, "ipv6": {"addresses": ["::ffff:1.2.3.4", "2606:4700::9"]}}}
asli = sc.probe_egress
try:
    sc.probe_egress = lambda url=None, timeout=8.0: FAKE
    s4 = r3.register("sasaran", kind="local")
    s4.proven = ["udp"]
    s4.unproven = ["spoof_src"]
    s4.na = ["tls13"]
    before = s4.probe_count
    r3.probe(s4.source_id)
    check("D cap prober lain (udp) tetap", "udp" in s4.proven, s4.proven)
    check("D cap prober lain (spoof_src) tetap", "spoof_src" in s4.unproven, s4.unproven)
    check("D cap PROBE_OWNED diganti hasil probe", "http1" in s4.proven and "tls13" not in s4.na, (s4.proven, s4.na))
    check("D probe_count & last_probe_at naik", s4.probe_count == before + 1 and s4.last_probe_at, s4.probe_count)
    check("D ip terisi dari IPv6 native (bukan mapped)", s4.ip == "2606:4700::9", s4.ip)
    check("D evidence tersimpan", "http_probe" in s4.evidence)
finally:
    sc.probe_egress = asli

print("== E. mark_proven (dua jalur) ==")
check("E mark_proven tersedia sebagai METODE registry (sejajar pick/probe)",
      hasattr(sc.SourceRegistry, "mark_proven"))

# jalur instance
s5 = r3.register("penanda", kind="worker")
s5.na = ["udp", "tls13"]
s5.unproven = ["spoof_src"]
r3.mark_proven(s5.source_id, ["udp", "spoof_src"], {"udp": {"ok": True}})
check("E jalur instance: cap pindah ke proven",
      set(["udp", "spoof_src"]).issubset(set(s5.proven)), s5.proven)
check("E jalur instance: dibersihkan dari na & unproven",
      "udp" not in s5.na and "spoof_src" not in s5.unproven, (s5.na, s5.unproven))
check("E jalur instance: evidence tergabung", s5.evidence.get("udp") == {"ok": True})

# jalur global (fungsi modul) - yang dipakai api.py
sg = sc.REGISTRY.register("penanda-global", kind="worker")
sg.unproven = ["udp"]
sc.mark_proven(sg.source_id, ["udp"])
check("E jalur global: fungsi modul menulis ke REGISTRY", "udp" in sg.proven, sg.proven)
check("E jalur global: instance lain tidak ikut berubah",
      r3.get("src-penanda-global") is None, r3.list())

try:
    sc.mark_proven("tidak-ada", ["udp"])
    check("E sumber tak ada -> SourceError", False, "tidak melempar")
except sc.SourceError:
    check("E sumber tak ada -> SourceError", True)

print("== F. matrix ==")
m = r3.matrix()
check("F matrix memuat capabilities", m["capabilities"] == list(sc.CAPABILITIES))
check("F matrix gaps per kapabilitas", set(m["gaps"].keys()) == set(sc.CAPABILITIES))
check("F matrix menyebut not_applicable", isinstance(m["not_applicable"], dict))

print("== G. ensure_local idempoten ==")
try:
    sc.probe_egress = lambda url=None, timeout=8.0: FAKE
    p1 = sc.ensure_local()
    p2 = sc.ensure_local()
    check("G idempoten (sumber sama)", p1.source_id == p2.source_id == "src-local-laptop", p1.source_id)
    check("G probe dijalankan tiap panggilan", p2.probe_count >= 2, p2.probe_count)
finally:
    sc.probe_egress = asli

print("== H. pengunci sumber ==")
src = open(os.path.join(ROOT, "backend", "srccap.py"), encoding="utf-8").read()
api = open(os.path.join(ROOT, "backend", "api.py"), encoding="utf-8").read()
check("H PROBE_OWNED tidak memuat udp/spoof_src",
      "udp" not in sc.PROBE_OWNED and "spoof_src" not in sc.PROBE_OWNED, sorted(sc.PROBE_OWNED))
check("H store_path menghormati GALARDO_SOURCES_PATH",
      "GALARDO_SOURCES_PATH" in src and sc.store_path().endswith("sources.json"))
check("H endpoint /sources ada (matrix/pick/register/probe/remove)",
      all(k in api for k in ('"/sources"', '"/sources/pick"', '"/sources/*"')))
check("H _pct aritmetika", sc._pct([], 50) is None and sc._pct([5], 50) == 5.0
      and sc._pct([1, 2, 3, 4], 0) == 1.0 and sc._pct([1, 2, 3, 4], 100) == 4.0)

shutil.rmtree(TMP, ignore_errors=True)
print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
