#!/usr/bin/env python3
"""Pengunci doktrin GOAL: docs/GOAL-GALARDO.md wajib ada, lengkap, dan dirujuk rantai onboarding."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'GOAL-GALARDO.md')

WAJIB_ISI = [
    '# DOKTRIN GOAL GALARDO',
    'TUJUAN (satu kalimat)',
    'DEFINISI SUKSES',
    'Reference #102',
    'LIMA PILAR',
    'multi-IP',
    'asimetri',
    'REA',
    'ANTI-POLA',
    'Sumbernya satu',
    'ATURAN KERJA',
]

RANTAI = ['ONBOARDING_PROMPT.md', 'ONBOARDING_PROMPT.txt', 'docs/SESSION_STATE.md',
          'docs/CONTEXT.md', 'docs/HANDOFF.md', 'docs/RESILIENCE.md', 'docs/INVENTARIS.md',
          'tools/resume.sh', 'tools/onboard.sh']

FAILS = []

def ok(cond, label, extra=''):
    if cond:
        print('  [ok]   ' + label)
    else:
        print('  [GAGAL] ' + label + ((' -> ' + str(extra)) if extra != '' else ''))
        FAILS.append(label)

ok(os.path.exists(DOC), 'docs/GOAL-GALARDO.md ada')
if not os.path.exists(DOC):
    print('  [GAGAL] verify_goal_doctrine: doktrin hilang')
    sys.exit(1)

isi = open(DOC, encoding='utf-8').read()
for m in WAJIB_ISI:
    ok(m in isi, 'doktrin memuat: %s' % m)

ada = 0
for rel in RANTAI:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        continue
    ada += 1
    t = open(p, encoding='utf-8', errors='replace').read()
    ok('GOAL-GALARDO' in t, 'rantai merujuk doktrin: %s' % rel)

ok(ada >= 4, 'rantai onboarding cukup (%d berkas ditemukan)' % ada, ada)
ok('docs/GOAL-GALARDO.md' in isi or 'GOAL-GALARDO.md' in isi, 'doktrin menamai dirinya sendiri')

if FAILS:
    print('  [GAGAL] verify_goal_doctrine: %d gagal' % len(FAILS))
    sys.exit(1)
print('  [ok]   verify_goal_doctrine: doktrin terpasang, lengkap, dan terikat ke rantai onboarding')
