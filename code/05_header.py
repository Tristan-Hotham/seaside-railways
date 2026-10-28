"""Step 5. Make header.png (1200x630 social card) by rendering a small HTML card with Playwright.

Usage: python3 code/05_header.py [font_dir]
Fonts come from Google Fonts; where that is unreachable, pass a folder holding FrauncesVar.ttf,
IBMPlexMono-Regular.ttf, IBMPlexMono-Medium.ttf and SourceSerif4-Regular.ttf.
"""
import asyncio
import csv
import json
import os
import sys

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "results.json")))
FONTS = sys.argv[1] if len(sys.argv) > 1 else None
pts = []
for r in csv.DictReader(open(os.path.join(ROOT, "data", "resorts.csv"), encoding="utf-8")):
    if r["lat"] and r["not_a_place"] == "False" and float(r["lon"]) > -6.2:
        pts.append([round(float(r["lat"]), 3), round(float(r["lon"]), 3), int(float(r["rail_year"])) if r["rail_year"] else 0])
dek = (f"Resorts were already growing {R['pre1831']['resort']['median']:.1f}% a year before any line reached them. "
       f"The line added a burst in the decade it opened.")
HTML = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,900&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400&display=swap">
<style>
body{margin:0;width:1200px;height:630px;background:#F5EFE1;color:#1D2328;overflow:hidden;position:relative;font-family:'Source Serif 4',Georgia,serif}
.l{position:absolute;left:72px;top:60px;width:640px}
.k{font:500 17px/1 'IBM Plex Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:#5E6468;display:flex;gap:14px;align-items:center}
.k b{background:#1C6B93;color:#fff;padding:8px 10px;font-weight:500}
h1{font:900 92px/.9 'Fraunces',Georgia,serif;letter-spacing:-.02em;margin:24px 0 0}
h1 em{font-style:normal;color:#1C6B93}
p{font-size:27px;line-height:1.34;margin:24px 0 0;color:#2A3035;max-width:560px}
.f{position:absolute;left:72px;bottom:34px;font:400 15px/1 'IBM Plex Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:#5E6468}
canvas{position:absolute;right:30px;top:12px}
</style></head><body>
<div class="l"><div class="k"><b>Data study</b><span>Britain, 1801 to 1911</span></div>
<h1>Did the railway invent the <em>seaside</em>?</h1>
<p>__DEK__</p></div>
<div class="f">Dr Tristan Hotham · Independent researcher</div>
<canvas id="c" width="840" height="1210" style="width:420px;height:605px"></canvas>
<script>
const P = __PTS__;
const cv = document.getElementById("c"), x = cv.getContext("2d"); x.scale(2, 2);
const k = Math.cos(54 * Math.PI / 180), lo0 = -6.2, lo1 = 1.9, la0 = 49.9, la1 = 58.7;
const sc = Math.min(420 / ((lo1 - lo0) * k), 605 / (la1 - la0));
const X = l => (l - lo0) * k * sc + (420 - (lo1 - lo0) * k * sc) / 2, Y = l => (la1 - l) * sc;
const C = ["#0B3550", "#1C6B93", "#3C8DB5", "#6FAECB", "#A6CCDD", "#D4B47A"];
P.sort((a, b) => b[2] - a[2]).forEach(([la, lo, y]) => { x.beginPath(); x.arc(X(lo), Y(la), 6, 0, 7);
  if (!y) { x.strokeStyle = "#B9B1A0"; x.lineWidth = 1.5; x.stroke(); return; }
  x.fillStyle = C[Math.max(0, Math.min(5, Math.floor((y - 1830) / 10)))]; x.fill(); x.strokeStyle = "#F5EFE1"; x.lineWidth = 1.2; x.stroke(); });
</script></body></html>"""
html = HTML.replace("__DEK__", dek).replace("__PTS__", json.dumps(pts))
if FONTS:
    css = "".join(f"@font-face{{font-family:'{fam}';src:url(file://{FONTS}/{f});font-weight:{w}}}" for fam, f, w in
                  [("Fraunces", "FrauncesVar.ttf", "100 900"), ("IBM Plex Mono", "IBMPlexMono-Regular.ttf", "400"),
                   ("IBM Plex Mono", "IBMPlexMono-Medium.ttf", "500"), ("Source Serif 4", "SourceSerif4-Regular.ttf", "400")])
    html = html.replace(html[html.index('<link rel="stylesheet"'):html.index("<style>")], f"<style>{css}</style>")


async def main():
    tmp = os.path.join(ROOT, "_header.html")
    open(tmp, "w", encoding="utf-8").write(html)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = await b.new_page(viewport={"width": 1200, "height": 630})
        await pg.goto("file://" + tmp)
        await pg.wait_for_timeout(1500)
        await pg.screenshot(path=os.path.join(ROOT, "header.png"))
        await b.close()
    os.remove(tmp)


asyncio.run(main())
print("header.png written")
