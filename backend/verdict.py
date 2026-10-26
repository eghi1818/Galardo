"""Galardo - verdict kematian berlapis (PROOF-OF-DEATH).

ATURAN MENGIKAT:
 1. Jangan pernah menyatakan mati tanpa >= 3 saksi dari 3 jaringan berbeda.
 2. Sebelum menyatakan mati, coba bantah dulu (falsifikasi).
 3. 'tidak ketemu' != 'tidak ada' -> tulis belum_konklusif, jangan dipaksa MODYAR.
 4. Kontradiksi antar-lapisan = TEMUAN, bukan error.
 5. Bedakan MATI_OVERRIDE (kita yang matikan) dari MATI_BEBAN (target mati sendiri).

Modul ini murni offline-testable (tidak menyentuh jaringan).
"""

from __future__ import annotations

__all__ = ["MODES", "LAPISAN", "klasifikasi", "niat", "keyakinan", "kontradiksi",
           "falsifikasi", "aturan_saksi", "verdict", "describe"]

LAPISAN = ["dns", "net", "tls", "edge", "origin", "app", "konten", "override"]

MODES = {
    "DNS_MATI": {"lapisan": "dns", "gejala": "NXDOMAIN / SERVFAIL / delegation hilang",
                 "akar": "zone, NS, registrar", "bukti": "jawaban 3 resolver"},
    "NET_MATI": {"lapisan": "net", "gejala": "TCP connect timeout, ICMP unreachable",
                 "akar": "rute, firewall, pipa", "bukti": "waktu connect"},
    "TLS_MATI": {"lapisan": "tls", "gejala": "handshake gagal / sertifikat kedaluwarsa",
                 "akar": "konfigurasi", "bukti": "fingerprint cert"},
    "EDGE_MATI": {"lapisan": "edge", "gejala": "CDN membalas halaman error sendiri",
                  "akar": "CDN", "bukti": "sidik jari error page"},
    "ORIGIN_MATI": {"lapisan": "origin", "gejala": "CDN membalas 520/521/522/523/524",
                    "akar": "origin tak menjawab", "bukti": "kode spesifik CF"},
    "APP_MATI": {"lapisan": "app", "gejala": "500/503 dari aplikasi, halaman brand sendiri",
                 "akar": "DB, worker, dependency", "bukti": "body halaman"},
    "KONTEN_HILANG": {"lapisan": "konten", "gejala": "404 / 410 sah",
                      "akar": "dihapus / dipensiunkan", "bukti": "410 = disengaja"},
    "SOFT_404": {"lapisan": "konten", "gejala": "200 tapi isi kosong/parkir",
                 "akar": "cloaking, domain dijual", "bukti": "kemiripan konten"},
    "MODYAR": {"lapisan": "semua", "gejala": "semua lapisan gagal, tak ada respons",
               "akar": "domain mati total", "bukti": "3 vantage, semua port"},
    "MATI_OVERRIDE": {"lapisan": "override", "gejala": "kita menyajikan override/404",
                      "akar": "Galardo (disengaja)", "bukti": "penanda override"},
    "HIDUP": {"lapisan": None, "gejala": "semua lapisan lolos", "akar": "-", "bukti": "-"},
}

FINGERPRINT_CDN = ("akamai_error", "cloudflare_error", "fastly_error", "varnish")
UJI_FALSIFIKASI = [
    "user-agent lain (bot vs browser)",
    "tanpa SNI dan dengan SNI",
    "versi TLS lain (1.2 vs 1.3)",
    "port alternatif (80, 8080, 8443)",
    "Host: header langsung ke IP origin",
    "ikuti redirect",
    "lewat proxy / jalur lain",
    "cek arsip (Wayback) - kalau ada, target pernah hidup",
    "cek status page penyedia",
]


def nilai_dari(payload):
    """Jembatan: panggil penilai utama apa pun namanya (dipakai endpoint/wiring)."""
    for nama in ("nilai", "klasifikasi", "classify", "hitung", "vonis"):
        fn = globals().get(nama)
        if callable(fn):
            try:
                return fn(**payload) if isinstance(payload, dict) else fn(payload)
            except TypeError:
                return fn(payload)
    return {"mode": "BELUM_ADA_PENILAI", "catatan": "verdict.py belum punya fungsi penilai"}


def _ok(bukti, kunci):
    d = bukti.get(kunci) or {}
    return d.get("ok") is not False


def aturan_saksi(bukti):
    """(jumlah_jaringan, konsisten, setuju) - saksi = vantage yang melaporkan."""
    vantage = bukti.get("vantage") or []
    jaringan = set()
    setuju = 0
    for v in vantage:
        jaringan.add(str(v.get("jaringan") or v.get("asn") or "?"))
        if v.get("ok") is False:
            setuju += 1
    konsisten = len({bool(v.get("ok")) for v in vantage}) == 1 if vantage else False
    return len(jaringan), konsisten, setuju


def kontradiksi(bukti):
    """Pola aneh yang HARUS dilaporkan sebagai temuan, bukan diabaikan."""
    out = []
    dns, tcp, tls, http = (bukti.get(k) or {} for k in ("dns", "tcp", "tls", "http"))
    if dns.get("ok") is True and tcp.get("ok") is True and tls.get("ok") is False:
        out.append("DNS ada, TCP nyambung, TLS gagal -> konfigurasi rusak")
    if http.get("cdn_status") == 200 and (bukti.get("origin") or {}).get("ok") is False:
        out.append("CDN bilang 200, origin gagal -> origin mati disembunyikan cache")
    if tcp.get("ok") is True and tls.get("ok") is False:
        out.append("HTTP jalan, HTTPS gagal -> sertifikat")
    if (bukti.get("ipv4") or {}).get("ok") is True and (bukti.get("ipv6") or {}).get("ok") is False:
        out.append("IPv4 jalan, IPv6 mati -> konfigurasi separuh")
    return out


def falsifikasi(bukti):
    """Daftar uji pembantah + hasilnya bila sudah dijalankan."""
    sudah = bukti.get("falsifikasi") or {}
    out = []
    for uji in UJI_FALSIFIKASI:
        out.append({"uji": uji, "hasil": sudah.get(uji),
                    "membatalkan": sudah.get(uji) is True})
    return out


def klasifikasi(bukti):
    """(mode, lapisan, alasan) - urut dari lapisan paling hulu."""
    if (bukti.get("override") or {}).get("aktif"):
        return "MATI_OVERRIDE", "override", "kita menyajikan override (disengaja)"

    http = bukti.get("http") or {}
    dns = bukti.get("dns") or {}
    tcp = bukti.get("tcp") or {}
    tls = bukti.get("tls") or {}

    gagal_total = (dns.get("ok") is False and tcp.get("ok") is False
                   and tls.get("ok") is False and http.get("ok") is False)
    if gagal_total:
        return "MODYAR", "semua", "DNS, TCP, TLS, HTTP semua gagal"
    if dns.get("nxdomain") or dns.get("ok") is False:
        return "DNS_MATI", "dns", "resolusi DNS gagal"
    if tcp.get("ok") is False:
        return "NET_MATI", "net", "TCP connect gagal"
    if tls.get("ok") is False:
        return "TLS_MATI", "tls", "handshake TLS gagal"
    fp = str(http.get("fingerprint") or "").lower()
    if any(f in fp for f in FINGERPRINT_CDN):
        return "EDGE_MATI", "edge", "halaman error milik CDN (%s)" % fp
    st = http.get("status")
    if isinstance(st, int) and 520 <= st <= 524:
        return "ORIGIN_MATI", "origin", "kode CDN %d (origin tak menjawab)" % st
    if isinstance(st, int) and st in (500, 502, 503, 504):
        return "APP_MATI", "app", "status aplikasi %d" % st
    if isinstance(st, int) and st in (404, 410):
        return "KONTEN_HILANG", "konten", "status %d sah" % st
    if st == 200 and (http.get("kemiripan_parkir") or 0) >= 0.8:
        return "SOFT_404", "konten", "200 tapi isi menyerupai parkir/kosong"
    return "HIDUP", None, "semua lapisan lolos"


def niat(bukti, mode):
    http = bukti.get("http") or {}
    if mode == "MATI_OVERRIDE":
        return "kita"
    if http.get("status") == 410:
        return "disengaja (pensiun)"
    if http.get("status") == 301 or http.get("redirect"):
        return "pindah"
    if mode == "SOFT_404":
        return "disengaja (domain dijual/parkir)"
    if (bukti.get("pola") or {}).get("burst_berulang"):
        return "pola serangan"
    if http.get("status") in (503, 502) or mode in ("NET_MATI", "MODYAR"):
        return "tidak disengaja"
    return "tidak diketahui"


def keyakinan(bukti):
    jaringan, konsisten, _ = aturan_saksi(bukti)
    if jaringan >= 3 and konsisten:
        return "tinggi"
    if jaringan >= 1:
        return "sedang"
    return "belum_konklusif"


def verdict(bukti, id_kejadian=None):
    mode, lapisan, alasan = klasifikasi(bukti)
    jaringan, konsisten, setuju = aturan_saksi(bukti)
    yak = keyakinan(bukti)
    belum = (jaringan < 3)
    return {
        "kejadian": id_kejadian or "KJ-?",
        "domain": bukti.get("domain"),
        "mode": mode,
        "lapisan": lapisan,
        "alasan": alasan,
        "niat": niat(bukti, mode),
        "vantage": {"jaringan": jaringan, "konsisten": konsisten, "setuju_mati": setuju},
        "keyakinan": ("belum_konklusif" if belum else yak),
        "belum_konklusif": belum,
        "catatan": ("butuh >= 3 saksi dari 3 jaringan sebelum menyatakan mati" if belum else None),
        "kontradiksi": kontradiksi(bukti),
        "falsifikasi": falsifikasi(bukti),
        "radius": bukti.get("radius") or {},
        "epoch_referensi": (bukti.get("http") or {}).get("epoch"),
        "referensi": (bukti.get("http") or {}).get("referensi"),
    }


def describe():
    return {"mode": sorted(MODES.keys()), "lapisan": LAPISAN,
            "aturan": ["3 saksi 3 jaringan", "falsifikasi dulu", "belum_konklusif bila ragu",
                       "kontradiksi = temuan", "MATI_OVERRIDE beda dari MATI_BEBAN"],
            "uji_falsifikasi": UJI_FALSIFIKASI}
