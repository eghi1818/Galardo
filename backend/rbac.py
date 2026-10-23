"""RBAC inti (item 8 / Tier 1). Rank peran + cek, fail-closed.

Kuat -> lemah: ADMIN > APPROVER > TEST_OPERATOR > VIEWER.
Peran tak dikenal -> rank 0 (tidak memenuhi apa pun).
min_role tak dikenal -> RbacError (fail-closed, bukan diam-diam lolos).
"""
from __future__ import annotations

ROLE_RANK = {"VIEWER": 1, "TEST_OPERATOR": 2, "APPROVER": 3, "ADMIN": 4, "SUPERADMIN": 5}
ROLES = tuple(sorted(ROLE_RANK, key=lambda r: -ROLE_RANK[r]))


class RbacError(Exception):
    pass


def rank(role):
    return ROLE_RANK.get((role or "").strip().upper(), 0)


def has_role(role, min_role):
    if min_role not in ROLE_RANK:
        raise RbacError("peran minimum tak dikenal: %r" % (min_role,))
    return rank(role) >= ROLE_RANK[min_role]


def _user_of_db(uid):
    """Ambil dokumen user dari db, toleran terhadap nama fungsi db yang berbeda."""
    if not uid:
        return None
    try:
        import db
    except Exception:
        return None
    for fn in ("get", "fetch", "find"):
        f = getattr(db, fn, None)
        if f:
            try:
                d = f("users", uid)
                if d:
                    return d
            except Exception:
                pass
    try:
        for d in db.all("users"):
            if d.get("id") == uid:
                return d
    except Exception:
        pass
    return None


def ensure(user_doc, min_role):
    """(ok, alasan). Fail-closed pada semua jalur."""
    if not user_doc:
        return False, "user tidak dikenal"
    status = (user_doc.get("status") or "ACTIVE")
    if status != "ACTIVE":
        return False, "status %s" % status
    role = user_doc.get("role")
    if not has_role(role, min_role):
        return False, "peran %s < %s" % (role, min_role)
    return True, "ok: %s rank %d >= %s" % (role, rank(role), min_role)


def public(user_doc):
    """Bentuk aman untuk dikirim ke UI."""
    if not user_doc:
        return None
    return {"id": user_doc.get("id"), "email": user_doc.get("email"),
            "role": user_doc.get("role"), "status": user_doc.get("status"),
            "org_id": user_doc.get("org_id"),
            "mfa_enabled": bool(user_doc.get("mfa_enabled"))}


def user_of(uid):
    """Cari pengguna di db, lalu jatuh ke penyimpanan kredensial."""
    rec = None
    try:
        rec = _user_of_db(uid)
    except Exception:
        rec = None
    if rec:
        return rec
    try:
        import users as _us
        u = _us.get(uid)
        if u:
            return {"id": uid, "username": u.get("username"), "name": u.get("name"),
                    "role": u.get("role"),
                    "status": "ACTIVE" if u.get("active", True) else "DISABLED"}
    except Exception:
        pass
    return None
