"""r/dataisbeautiful collage for Seaside Railways. Reads only ../data/ and the Natural Earth land polygons.
Usage (from anywhere): python3 reddit/collage.py [font_dir]
"""
import json
import os
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "data")
F = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/-home-claude/c232619d-81e0-53f3-9de6-41e973630753/scratchpad/fonts"
for f in ["FrauncesVar.ttf", "IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf", "SourceSerif4-Regular.ttf", "SourceSerif4-Semibold.ttf", "SourceSerif4-It.ttf"]:
    fm.fontManager.addfont(os.path.join(F, f))
DISP = fm.FontProperties(fname=os.path.join(F, "FrauncesVar.ttf"), weight=900)
SER, MONO = "Source Serif 4", "IBM Plex Mono"
BG, SEAB, LANDC, LANDE = "#F6EFDF", "#DCEBF1", "#F2E6CB", "#D6C49C"
FG, MUT = "#1D2328", "#5A6166"
SEA, INL, RAIL, WD = "#1C6B93", "#B06A26", "#B23A2E", "#8C8F86"
DEC = ["#0B3550", "#1C6B93", "#3C8DB5", "#6FAECB", "#A6CCDD", "#D9AE62"]
DECLAB = ["1830s", "1840s", "1850s", "1860s", "1870s", "1880 to 1909"]
R = json.load(open(os.path.join(D, "results.json")))
RS = pd.read_csv(os.path.join(D, "resorts.csv"))
P = pd.read_csv(os.path.join(D, "places.csv"))
K = np.cos(np.radians(54))

land = []
for ft in json.load(open("/home/claude/hist/_data3/ne/geojson/ne_10m_land.geojson"))["features"]:
    g = ft["geometry"]
    for p in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
        r = np.array(p[0])
        if ((r[:, 0] > -11) & (r[:, 0] < 3) & (r[:, 1] > 49) & (r[:, 1] < 61)).any():
            land.append(r)


def dcol(y):
    return DEC[max(0, min(5, (int(y) - 1830) // 10))]


fig = plt.figure(figsize=(12, 15), dpi=200)
fig.patch.set_facecolor(BG)
fig.text(0.04, 0.968, "Did the railway", fontproperties=DISP, fontsize=54, color=FG, va="top")
fig.text(0.04, 0.918, "invent the seaside?", fontproperties=DISP, fontsize=54, color=SEA, va="top")
fig.text(0.04, 0.862, f"{R['coverage']['resorts_with_census']} British seaside resorts through every census from 1801 to 1911, lined up\n"
                      f"against the year their first railway station opened, and set against inland towns.",
         family=SER, fontsize=15.5, color=FG, va="top", linespacing=1.4)

# ---- hero map
ax = fig.add_axes([0.0, 0.365, 0.6, 0.45])
ax.set_facecolor(SEAB)
for r in land:
    ax.add_patch(Polygon(np.c_[r[:, 0] * K, r[:, 1]], fc=LANDC, ec=LANDE, lw=0.5))
pl = RS[(~RS.not_a_place) & RS.lat.notna() & (RS.lon > -8.3)]
big = P[P.group == "resort"].set_index("place")
for r in pl.sort_values("rail_year", ascending=False, na_position="first").itertuples():
    sz = 34
    if r.list_name in big.index and not pd.isna(big.loc[r.list_name, "pop1911"]):
        sz = max(60, min(700, np.sqrt(big.loc[r.list_name, "pop1911"]) * 2.4))
    if pd.isna(r.rail_year):
        ax.scatter(r.lon * K, r.lat, s=30, facecolor="none", edgecolor=WD, lw=1.1, zorder=3)
    else:
        ax.scatter(r.lon * K, r.lat, s=sz, color=dcol(r.rail_year), edgecolor="white", lw=0.7, zorder=4)
LABS = {"Blackpool": (-4.4, 0.55, "Blackpool 1846"), "Skegness": (0.45, 0.25, "Skegness 1873"), "Brighton": (-0.6, -0.55, "Brighton 1841"),
        "Weston-super-Mare": (-3.2, 0.55, "Weston 1841"), "Scarborough": (0.5, 0.2, "Scarborough 1845"),
        "Llandudno": (-2.6, 0.55, "Llandudno 1858"), "Torquay": (-0.9, -0.55, "Torquay 1848"), "Frinton-on-Sea": (0.45, -0.45, "Frinton 1866")}
for nm, (dx, dy, lab) in LABS.items():
    r = pl[pl.list_name == nm].iloc[0]
    ax.annotate(lab, (r.lon * K, r.lat), (r.lon * K + dx * K, r.lat + dy), fontsize=11.5, family=MONO, color=FG,
                arrowprops=dict(arrowstyle="-", color=FG, lw=0.7), zorder=6)
ax.set_xlim(-6.6 * K, 2.3 * K)
ax.set_ylim(49.85, 58.75)
ax.set_aspect(1)
ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)
h = [Line2D([], [], marker="o", ls="", color=c, ms=10, label=l) for c, l in zip(DEC, DECLAB)]
h.append(Line2D([], [], marker="o", ls="", mfc="none", mec=WD, ms=9, label="no station within 3 km"))
fig.legend(handles=h, loc="lower left", bbox_to_anchor=(0.035, 0.30), ncol=4, frameon=False, prop={"family": MONO, "size": 11},
           title="first station within 3 km  ·  bigger circles: resorts with census figures, sized by 1911 population",
           title_fontproperties={"family": MONO, "size": 10.5}, alignment="left", columnspacing=1.2, handletextpad=0.3)

# ---- headline numbers
tx = fig.add_axes([0.62, 0.37, 0.36, 0.44])
tx.axis("off")
pre = R["pre1831"]
nums = [(f"{pre['resort']['median']:.1f}% a year", f"typical resort growth 1801 to 1831,\nbefore any railway reached them.\nInland towns: {pre['inland']['median']:.1f}%. Villages: {pre['inland_wikidata']['median']:.1f}%."),
        (f"+{R['reg']['resort_event'][4]['coef']:.1f} points", "extra growth a year in the decade the\nline opened, against the decade before.\nNo build-up beforehand."),
        (f"{R['per_place']['resort']['n_faster_after']} of {R['per_place']['resort']['n']}",
         "resorts grew faster after the railway.\nThe pre-railway boom towns (Weston,\nTorquay, Brighton) slowed down."),
        (f"{R['arrival']['y1840s']}", f"resorts got their first station in the\n1840s. Near the big industrial towns:\nmedian {R['distance']['bands'][0]['median_year']}. Over 150 km away: {R['distance']['bands'][3]['median_year']}.")]
y = 0.985
for big_, small in nums:
    tx.text(0, y, big_, fontproperties=DISP, fontsize=33, color=SEA if not big_.startswith("+") else RAIL, va="top", transform=tx.transAxes)
    tx.text(0, y - 0.085, small, family=SER, fontsize=13, color=FG, va="top", transform=tx.transAxes, linespacing=1.35)
    y -= 0.255

# ---- event chart
ex = fig.add_axes([0.075, 0.145, 0.42, 0.125])
ex.set_facecolor(BG)
ex.axvspan(-0.5, 0.5, color=RAIL, alpha=0.13, lw=0)
for gname, lab, c, lw in [("inland", "inland towns", INL, 2), ("resort", "seaside resorts", SEA, 3)]:
    e = R["event"][gname]
    ex.plot([x["k"] for x in e], [x["mean"] for x in e], "-o", color=c, lw=lw, ms=5, label=lab)
ex.text(0.65, 3.45, "railway opens", color=RAIL, fontsize=10.5, family=MONO, ha="left", va="center")
ex.set_ylim(0, 3.8)
ex.set_xlabel("census decades before and after the railway", fontsize=11, family=MONO, color=MUT)
ex.set_ylabel("growth % a year", fontsize=11, family=MONO, color=MUT)
ex.tick_params(labelsize=10.5, colors=MUT)
for s in ("top", "right"):
    ex.spines[s].set_visible(False)
ex.legend(fontsize=10.5, frameon=False, loc="upper left", prop={"family": MONO, "size": 10.5})
fig.text(0.04, 0.287, "BEFORE AND AFTER THE LINE  ·  mean growth by census decade", family=MONO, fontsize=11.5, color=MUT)

# ---- three cases
fig.text(0.56, 0.287, "THREE RESORTS  ·  population, log scale", family=MONO, fontsize=11.5, color=MUT)
for i, nm in enumerate(["Skegness", "Weston-super-Mare", "Brighton"]):
    c = R["cases"][nm]
    s = [x for x in c["series"] if x["pop"] > 0]
    a = fig.add_axes([0.575 + i * 0.14, 0.145, 0.11, 0.105])
    a.set_facecolor(BG)
    yrs, vals = [x["year"] for x in s], [x["pop"] for x in s]
    seg = [[0]]
    for j in range(1, len(s)):
        if yrs[j] - yrs[j - 1] > 10:
            seg.append([])
        seg[-1].append(j)
    for sg in seg:
        a.plot([yrs[j] for j in sg], [vals[j] for j in sg], color=SEA, lw=2.4)
    a.axvline(c["rail_year"], color=RAIL, lw=1.8)
    a.set_yscale("log")
    a.set_xlim(1795, 1916)
    a.set_xticks([1801, 1911], ["1801", "1911"])
    a.tick_params(labelsize=9.5, colors=MUT)
    a.set_yticks([])
    a.minorticks_off()
    for sp in ("top", "right", "left"):
        a.spines[sp].set_visible(False)
    short = "Weston" if nm.startswith("Weston") else nm
    a.set_title(f"{short}\n{vals[0]:,} to {vals[-1]:,}", fontsize=11.5, family=SER, color=FG, loc="left", pad=4)
    a.text(c["rail_year"] + 3, 0.02, f"rail\n{c['rail_year']}", color=RAIL, fontsize=9.5, family=MONO, va="bottom", transform=a.get_xaxis_transform())

fig.text(0.04, 0.012, "Data: census populations of each resort's parish or township, from A Vision of Britain through Time (University of Portsmouth);\n"
                      "resort list and articles from Wikipedia (CC BY-SA 4.0); station opening dates and village figures from Wikidata (CC0);\n"
                      "OS Open Names (OGL v3, contains OS data © Crown copyright 2026); Natural Earth. Railway = first station within 3 km.\n"
                      "Partial coverage (68 of 201 resorts in Great Britain have census series); association, not cause.\n"
                      "Analysis and chart: Tristan Hotham, with Python and matplotlib.",
         family=MONO, fontsize=9.6, color=MUT, linespacing=1.5)
out = os.path.join(HERE, "did_the_railway_invent_the_seaside.png")
fig.savefig(out, dpi=200, facecolor=BG)
print("saved", out)
