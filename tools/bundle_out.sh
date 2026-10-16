#!/bin/bash
# Pecah bundel .md kembali jadi file asli. Backup .bak otomatis.
# Pakai: bash tools/bundle_out.sh BUNDEL.md
IN="$1"
[ -z "$IN" ] && { echo "pakai: bash tools/bundle_out.sh BUNDEL.md"; exit 1; }
[ ! -f "$IN" ] && { echo "tidak ada: $IN"; exit 1; }
python3 - "$IN" <<'PYEOF'
import os, sys, re
src = sys.argv[1]
text = open(src, "r", encoding="utf-8", errors="replace").read()
pat = re.compile(r"^=== FILE: (.+?) ===\n(.*?)\n?=== END FILE: \1 ===$",
                 re.M | re.S)
n = 0
for m in pat.finditer(text):
    path, body = m.group(1).strip(), m.group(2)
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, 0o755)
    if os.path.exists(path):
        os.replace(path, path + ".bak")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body + "\n")
    print("  tulis: %s" % path)
    n += 1
print("selesai: %d file" % n)
PYEOF
