"""Step 4. Build index.html from code/page_template.html.

Every number in the text is a {{path|format}} token filled from data/results.json, so the page cannot drift from the
analysis. Map and chart data (_site_data.json from step 3) and the parts of results.json the charts need are embedded,
so the page works as a single file. _site_data.json is removed afterwards.

Usage: python3 code/04_build_page.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "results.json"), encoding="utf-8"))
SITE_PATH = os.path.join(ROOT, "_site_data.json")
SITE = open(SITE_PATH, encoding="utf-8").read()
tpl = open(os.path.join(ROOT, "code", "page_template.html"), encoding="utf-8").read()


def get(path):
    v = R
    for k in path.split("."):
        v = v[int(k)] if isinstance(v, list) else v[k]
    return v


def fmt(v, f):
    if f is None or f == "raw":
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    if f == "int":
        return f"{round(v):,}"
    if f == "pct":
        return f"{round(v * 100)}%"
    if f == "f1":
        return f"{v:.1f}"
    if f == "f2":
        return f"{v:.2f}"
    if f == "f3":
        return f"{v:.3f}"
    if f == "x1":
        return f"{v:.1f}"
    if f == "sf1":
        return f"{v:+.1f}"
    if f == "sf2":
        return f"{v:+.2f}"
    raise ValueError(f)


used = []


def sub(m):
    used.append(m.group(1))
    return fmt(get(m.group(1)), m.group(3))


if __name__ == "__main__":
    html = re.sub(r"\{\{([^}|]+)(\|(\w+))?\}\}", sub, tpl)
    slim = {k: R[k] for k in ["arrival", "distance", "pre1831", "event", "reg", "long", "cases", "per_place"]}
    html = html.replace("/*SITE*/", SITE).replace("/*RESULTS*/", json.dumps(slim, ensure_ascii=False, separators=(",", ":")))
    assert "{{" not in html
    for bad in ("—", "–"):
        assert bad not in html, bad
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html", len(html.encode()), "bytes;", len(used), "tokens filled")
    os.remove(SITE_PATH)
