"""Pencatatan IP egress per worker + jembatan ke gateway Mode B.

Doktrin: "ribuan IP" harus menjadi FAKTA, bukan klaim. Modul ini menyimpan IP egress
terakhir yang terlihat per worker supaya bisa ditampilkan dan dibuktikan.

Catatan: pencatatan di sini berbasis pemanggilan note(); hook ke loop worker menyusul
kalau diagnosa menunjukkan transport belum memakai pool.
"""
import threading
import time

import gateway

_LOCK = threading.Lock()
_LAST = {}
_SEEN = {}


def enabled():
    return gateway.enabled()


def proxies():
    """dict untuk requests/urllib, atau None bila gateway tidak aktif."""
    if not gateway.enabled():
        return None
    u = gateway.proxy_url()
    return {'http': u, 'https': u}


def record(worker, ip):
    if not worker or not ip:
        return
    now = time.time()
    w = str(worker)
    i = str(ip)
    with _LOCK:
        _LAST[w] = {'ip': i, 'ts': now}
        _SEEN[i] = _SEEN.get(i, 0) + 1


def note(worker=None, timeout=15):
    """Ambil IP egress lewat gateway lalu catat. Kembalikan ip, 'ERR:*', atau None."""
    if not gateway.enabled():
        return None
    try:
        ip = gateway.egress_ip(timeout=timeout)
    except Exception as e:
        return 'ERR:' + type(e).__name__
    record(worker, ip)
    return ip


def snapshot():
    with _LOCK:
        return {'enabled': gateway.enabled(), 'sticky': gateway.sticky(),
                'worker_tercatat': len(_LAST), 'ip_unik': len(_SEEN),
                'ip_unik_daftar': sorted(_SEEN), 'terakhir': dict(_LAST)}


def reset():
    with _LOCK:
        _LAST.clear()
        _SEEN.clear()
