"""Helper used while collecting census figures: append one A Vision of Britain through Time unit page,
as transcribed, to data/vob_transcriptions.tsv.

Usage: python3 code/vob_add.py "<place>" "<group: resort|inland>" "<page url>" <<'EOF'
UNIT: ...
YEAR|EARLIER|CURRENT
...
EOF

Each row keeps the place, the unit, the page URL, the census year and the two figures exactly as transcribed.
For pages that only show males and females (MODE gender), CURRENT is males + females and EARLIER is blank.
"""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(ROOT, "data", "vob_transcriptions.tsv")
place, group, url = sys.argv[1], sys.argv[2], sys.argv[3]
mode = sys.argv[4] if len(sys.argv) > 4 else "total"
txt = sys.stdin.read()
unit = re.search(r"UNIT:\s*(.+)", txt).group(1).strip()
uid = re.search(r"/unit/(\d+)", url).group(1)
canon = f"https://www.visionofbritain.org.uk/unit/{uid}/cube/{'TOT_POP' if mode == 'total' else 'GENDER'}"
new = not os.path.exists(F)
rows = []
for ln in txt.splitlines():
    m = re.match(r"\s*(1[89]\d\d)\|([\d,]*)\|([\d,]*)(?:\|([\d,]*))?", ln)
    if not m:
        continue
    y, a, b = m.group(1), m.group(2).replace(",", ""), m.group(3).replace(",", "")
    if mode == "gender":
        tot = (m.group(4) or "").replace(",", "")
        earlier, current = "", tot or (str(int(a) + int(b)) if a and b else "")
    else:
        earlier, current = a, b
    rows.append([place, group, uid, unit, canon, y, earlier, current, mode])
with open(F, "a", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter="\t")
    if new:
        w.writerow(["place", "group", "vob_unit_id", "vob_unit", "url", "year", "earlier", "current", "mode"])
    w.writerows(rows)
print(place, unit, len(rows), "rows")
