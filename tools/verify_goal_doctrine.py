#!/usr/bin/env python3
"""Pengunci doktrin GOAL: docs/GOAL-GALARDO.md wajib ada, lengkap, dan dirujuk rantai onboarding."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'GOAL-GALARDO.md')

WAJIB_ISI = [
    '# DOKTRIN GOAL GALARDO', 'Berkas ini', 'TUJUAN (satu kalimat)', 'DEFINISI SUKSES',
    'Reference #102', 'LIMA PILAR', 'multi-IP', 'asimetri', 'REA', 'ANTI-POLA',
    'Sumbernya satu', 'ATURAN KERJA',
]

RANTAI_WAJIB = ['docs/SESSION_STATE.md', 'docs/CONTEXT.md', 'docs/HANDOFF.md',
                'docs/RESILIENCE.md', 'docs/INVENTARIS.md', 'tools/resume.sh', 'tools/onboard.sh']

FAILS = []

def ok(cond, label, extra=''):
    if cond:
        print('  [ok]   ' + label)
    else:
        print('  [GAGAL] ' + label + ((' -> ' + str(extra)) if extra != '' else ''))
        FAILS.append(label)

def baca(p):
    try:
        return open(p, encoding='utf-8', errors='replace').read()
    except Exception:
        return ''

ok(os.path.exists(DOC), 'docs/GOAL-GALARDO.md ada')
if not os.path.exists(DOC):
    print('  [GAGAL] verify_goal_doctrine: doktrin hilang')
    sys.exit(1)

isi = baca(DOC)
for m in WAJIB_ISI:
    ok(m in isi, 'doktrin memuat: %s' % m)
ok('Berkas ini' in isi and 'docs/GOAL-GALARDO.md' in isi, 'doktrin menamai dirinya sendiri')

ada = 0
for rel in RANTAI_WAJIB:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        continue
    ada += 1
    ok('GOAL-GALARDO' in baca(p), 'rantai merujuk doktrin: %s' % rel)
ok(ada >= 4, 'rantai onboarding cukup (%d berkas ditemukan)' % ada, ada)

onb = []
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d not in ('.git', '.out', 'node_modules', '__pycache__')]
    for f in fn:
        if 'ONBOARDING' in f.upper():
            onb.append(os.path.join(dp, f))
ok(bool(onb), 'berkas onboarding ada di repo (%d)' % len(onb))
ok(any('GOAL-GALARDO' in baca(p) for p in onb) if onb else False, 'berkas onboarding merujuk doktrin')

if FAILS:
    print('  [GAGAL] verify_goal_doctrine: %d gagal' % len(FAILS))
    sys.exit(1)
print('  [ok]   verify_goal_doctrine: doktrin terpasang, lengkap, terikat ke rantai onboarding')
