#!/usr/bin/env python3
"""Tes offline modul rbac (item 8 / Tier 1). Tanpa jaringan, tanpa db."""
import os, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import rbac

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s   <-- %r" % (name, detail))


U = lambda role, status="ACTIVE": {"id": "u1", "role": role, "status": status}

print("== A. rank ==")
check("A rank ADMIN = 4", rbac.rank("ADMIN") == 4)
check("A rank viewer huruf kecil", rbac.rank("viewer") == 1)
check("A rank tak dikenal = 0", rbac.rank("SUPERMAN") == 0)
check("A rank None = 0", rbac.rank(None) == 0)
check("A ROLES urut kuat ke lemah",
      list(rbac.ROLES) == sorted(rbac.ROLES, key=lambda r: -rbac.ROLE_RANK[r]), rbac.ROLES)

print("== B. has_role ==")
check("B ADMIN >= APPROVER", rbac.has_role("ADMIN", "APPROVER") is True)
check("B VIEWER >= ADMIN salah", rbac.has_role("VIEWER", "ADMIN") is False)
check("B TEST_OPERATOR >= TEST_OPERATOR", rbac.has_role("TEST_OPERATOR", "TEST_OPERATOR") is True)
check("B peran tak dikenal gagal", rbac.has_role("SUPERMAN", "VIEWER") is False)
try:
    rbac.has_role("ADMIN", "SUPERMAN")
    check("B min_role tak dikenal -> RbacError", False, "tidak melempar")
except rbac.RbacError:
    check("B min_role tak dikenal -> RbacError", True)

print("== C. ensure (fail-closed) ==")
check("C user None -> gagal", rbac.ensure(None, "VIEWER")[0] is False)
check("C status non-ACTIVE -> gagal", rbac.ensure(U("ADMIN", "SUSPENDED"), "VIEWER")[0] is False)
check("C peran kurang -> gagal", rbac.ensure(U("VIEWER"), "APPROVER")[0] is False)
ok, why = rbac.ensure(U("APPROVER"), "APPROVER")
check("C peran cukup -> ok", ok is True, why)
ok2, why2 = rbac.ensure(U("ADMIN"), "TEST_OPERATOR")
check("C alasan memuat rank", ok2 is True and "rank 4" in why2, why2)
check("C alasan gagal memuat peran", "VIEWER" in rbac.ensure(U("VIEWER"), "ADMIN")[1])

print("== D. public() ==")
p = rbac.public(U("ADMIN"))
check("D public memuat id/role/status", set(["id", "role", "status"]).issubset(p.keys()), p)
check("D public None -> None", rbac.public(None) is None)

print()
print("RESULTS: %d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
