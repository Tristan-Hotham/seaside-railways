"""Step 2. Census populations 1801 to 1911 and decade growth intervals.

Reads:
  data/vob_transcriptions.tsv   census figures for each place's parish (or township), as shown on the
                                "Total Population" (or "Males & Females") pages of A Vision of Britain through Time
                                (University of Portsmouth), collected with code/vob_add.py. Each row keeps the
                                unit, the page URL and the figures exactly as transcribed.
  data/resorts.csv              from step 1
  _data9/wd_osm_bundle.json     wd_historic_populations_tsv: Wikidata population statements dated before 1950 (CC0),
                                used for a second inland comparison group (mostly Cambridgeshire and Huntingdonshire parishes)
  _data9/wikipedia_wikitext.json  "List of towns and cities in England by historical population" (CC BY-SA 4.0), for checks
  _data11/wikipedia_batch11.json.gz  resort articles (CC BY-SA 4.0), for checks and one extra 1801 figure (Blackpool)
  _data11/wd_osm_bundle11.json.gz    Wikidata stations (railway dates for the inland groups)
  osnames_gb.tsv                OS Open Names (inland town points)
  _data3/ne/geojson/ne_10m_coastline.geojson  Natural Earth coastline (distance to the sea)

Writes:
  data/populations.csv   one row per place and census year: population, the figure for ten years earlier on the
                         same boundary (where the source gives it), source and URL
  data/intervals.csv     one row per place and ten-year interval with a usable pair of figures: start and end
                         population on the same boundary, annual growth rate (log points per year x 100)
  data/places.csv        one row per place in the analysis (resorts and inland towns): point, railway year and station
  data/checks.json       cross-checks of the transcriptions against figures quoted on Wikipedia

Rules for intervals (the heart of the method):
  * Growth over a decade is measured between the "population ten years earlier" figure printed on a census row
    (restated on that census's boundary) and the population at that census. This keeps each pair on one boundary.
  * Where the source gives no restated figure, the previous census's own figure is used (flagged "consecutive").
  * The parish tables for England and Wales skip 1861 (and give 1871 only as the restated "earlier" figure on the
    1881 row). I do not bridge 1851 to 1871, because a boundary change in between would look like growth or loss.
    So English and Welsh places lose the 1851 to 1871 span; Scottish parishes keep it.
  * Only censuses up to 1911 are used.
"""
import csv
import gzip
import json
import math
import os
import re
from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = "/home/claude/hist"
D = os.path.join(ROOT, "data")
KX, KY = 111.32 * math.cos(math.radians(53)), 110.57
YEARS = [1801, 1811, 1821, 1831, 1841, 1851, 1861, 1871, 1881, 1891, 1901, 1911]

# ---------------- 1. Vision of Britain transcriptions
rows = list(csv.DictReader(open(os.path.join(D, "vob_transcriptions.tsv"), encoding="utf-8"), delimiter="\t"))
pop = defaultdict(dict)       # place -> year -> (current, earlier)
meta = {}
for r in rows:
    y = int(r["year"])
    if y > 1911:
        continue
    cur = int(r["current"]) if r["current"] else None
    ear = int(r["earlier"]) if r["earlier"] else None
    pop[r["place"]][y] = (cur, ear)
    meta[r["place"]] = {"group": r["group"], "vob_unit": r["vob_unit"], "vob_unit_id": r["vob_unit_id"], "url": r["url"], "mode": r["mode"]}

# Blackpool: the census unit found starts in 1911, so its 1801 figure comes from the resort article (quoted below)
EXTRA = {("Blackpool", 1801): (473, "Wikipedia, Blackpool: \"By 1801, the population reached 473\"")}

# ---------------- 2. checks against figures quoted on Wikipedia
W = json.load(gzip.open(f"{H}/_data11/wikipedia_batch11.json.gz"))["articles"]
TL = json.load(open(f"{H}/_data9/wikipedia_wikitext.json", encoding="utf-8"))["List of towns and cities in England by historical population"]["text"]
QUOTES = [  # (place, year, figure, article, exact text that must appear in the article)
    ("Brighton", 1801, 7339, "Brighton", "from 7,339 in 1801 to 46,661 in 1841"),
    ("Brighton", 1841, 46661, "Brighton", "from 7,339 in 1801 to 46,661 in 1841"),
    ("Skegness", 1801, 134, "Skegness", "recorded a population of 134"),
    ("Skegness", 1911, 3775, "Skegness", "By 1911, the population had reached 3,775"),
    ("Great Yarmouth", 1801, 14845, "List of towns and cities in England by historical population", "[[Great Yarmouth]]||14,845"),
]
checks = []
for place, y, fig, art, txt in QUOTES:
    src = TL if art.startswith("List of towns") else W[art]["text"]
    assert txt in src, (place, txt)
    got = pop[place][y][0]
    checks.append({"place": place, "year": y, "wikipedia": fig, "vision_of_britain": got, "match": got == fig, "article": art, "quote": txt})
assert "By 1801, the population reached 473" in W["Blackpool"]["text"]
print("checks:", [(c["place"], c["year"], c["match"]) for c in checks])

# internal consistency: where a row's "earlier" figure should equal the previous census's own figure
# (no boundary change), how often do they agree?
agree = differ = 0
for p, s in pop.items():
    for y in YEARS[1:]:
        if y in s and (y - 10) in s and s[y][1] is not None and s[y - 10][0] is not None:
            if s[y][1] == s[y - 10][0]:
                agree += 1
            else:
                differ += 1
checks_summary = {"n_checks": len(checks), "n_match": sum(c["match"] for c in checks), "checks": checks,
                  "pairs_earlier_equals_previous": agree, "pairs_earlier_differs": differ}

# ---------------- 3. places: resorts + inland towns, points and railway dates
res = {r["list_name"]: r for r in csv.DictReader(open(os.path.join(D, "resorts.csv"), encoding="utf-8"))}
def plain(t):
    t = re.sub(r"<ref.*?(</ref>|/>)", "", t, flags=re.S)
    return re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)


# Inland towns whose earliest Wikidata station date within 3 km is a rebuilding or reopening date. Corrected from the
# English Wikipedia station articles (read on 28 October 2026; the quoted words are from those articles).
INLAND_OVERRIDE = {
    "Loughborough": (1840, "https://en.wikipedia.org/wiki/Loughborough_railway_station", "The original station was opened in 1840 by the Midland Counties Railway"),
    "Berkhamsted": (1838, "https://en.wikipedia.org/wiki/Berkhamsted_railway_station", "The original station building, opened in 1838"),
    "Leighton Buzzard": (1838, "https://en.wikipedia.org/wiki/Leighton_Buzzard_railway_station", "The first station simply known as 'Leighton' was opened by the London and Birmingham Railway on 9 April 1838."),
    "Evesham": (1852, "https://en.wikipedia.org/wiki/Evesham_railway_station", "opened to public traffic on 3 May 1852"),
    "Llanfair Caereinion": (1903, "https://en.wikipedia.org/wiki/Llanfair_Caereinion_railway_station", "The station was opened on 6 April 1903."),
}
def plain(t):
    t = re.sub(r"<ref.*?(</ref>|/>)", "", t, flags=re.S)
    return re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)


# station list for inland places
B = json.load(gzip.open(f"{H}/_data11/wd_osm_bundle11.json.gz"))["results"]
st = {}
for line in B["wd_stations"]["tsv"].split("\n")[1:]:
    p = line.split("\t")
    if len(p) < 5 or not p[3]:
        continue
    m = re.search(r"POINT\(([-\d.]+) ([-\d.]+)\)", p[2])
    yy = re.match(r"(\d{4})", p[3])
    if not m or not yy:
        continue
    q = p[0].rsplit("/", 1)[-1].rstrip(">")
    if q not in st or int(yy.group(1)) < st[q][3]:
        st[q] = (re.sub(r'^"|"@en$', "", p[1]), float(m.group(1)), float(m.group(2)), int(yy.group(1)))
SP = np.array([(v[1] * KX, v[2] * KY) for v in st.values()])
SV = list(st.values())
stree = cKDTree(SP)


def rail(lat, lon, rad=3.0):
    idx = stree.query_ball_point((lon * KX, lat * KY), rad)
    if not idx:
        return None, "", None
    best = min(idx, key=lambda i: (SV[i][3], 0))
    d = math.hypot(SV[best][1] * KX - lon * KX, SV[best][2] * KY - lat * KY)
    return SV[best][3], SV[best][0], round(d, 2)


coast = []
for ft in json.load(open(f"{H}/_data3/ne/geojson/ne_10m_coastline.geojson", encoding="utf-8"))["features"]:
    g = ft["geometry"]
    for ln in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]):
        if any(-8 < x < 2.5 and 49.5 < y < 59 for x, y in ln):
            coast.extend(ln)
ctree = cKDTree(np.array([(x * KX, y * KY) for x, y in coast]))

# inland town points from OS Open Names (the sampled town names; see code/00_inland_sample.py)
osn = {}
INLAND = {m["group"] for m in meta.values()}
inland_names = [p for p, m in meta.items() if m["group"] == "inland"]
with open(f"{H}/osnames_gb.tsv", encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["type"] == "populatedPlace" and r["local_type"] == "Town" and r["name1"] in inland_names and r["country"] in ("England", "Wales"):
            osn.setdefault(r["name1"], r)

places = []
for p, m in meta.items():
    if m["group"] == "resort":
        r = res[p]
        lat, lon = float(r["lat"]), float(r["lon"])
        ry = int(float(r["rail_year"])) if r["rail_year"] else None
        rsrc = r["rail_source"]
        places.append({"place": p, "group": "resort", "article": r["title"], "country": r["country"], "lat": lat, "lon": lon,
                       "coord_source": r["coord_source"], "rail_year": ry, "rail_source": rsrc,
                       "rail_year_wikidata_3km": r["rail_year_3km"] and int(float(r["rail_year_3km"])), "rail_station": r["rail_station"]})
    else:
        o = osn[p]
        lat, lon = float(o["lat"]), float(o["lon"])
        ry, sname, sd = rail(lat, lon)
        wdy = ry
        rsrc = f"Wikidata: earliest opening date of a station within 3 km ({sname})" if ry else ""
        if p in INLAND_OVERRIDE:
            ry = INLAND_OVERRIDE[p][0]
            rsrc = f'Wikipedia station article {INLAND_OVERRIDE[p][1]}: "{INLAND_OVERRIDE[p][2]}"'
        places.append({"place": p, "group": "inland", "article": "", "country": o["country"], "lat": lat, "lon": lon,
                       "coord_source": f'OS Open Names ({o["name1"]}, Town, {o["district"] or o["county"]})', "rail_year": ry,
                       "rail_source": rsrc, "rail_year_wikidata_3km": wdy, "rail_station": sname})
for pl in places:
    pl["km_to_sea"] = round(float(ctree.query((pl["lon"] * KX, pl["lat"] * KY))[0]), 1)
    pl.update(meta[pl["place"]])

# ---------------- 4. Wikidata parishes (second inland group)
WD = json.load(open(f"{H}/_data9/wd_osm_bundle.json", encoding="utf-8"))["wd_historic_populations_tsv"].split("\n")
wdser = defaultdict(dict)
wdlab, wdco = {}, {}
for ln in WD[1:]:
    p = ln.split("\t")
    if len(p) < 5:
        continue
    y = re.match(r"(\d{4})", p[4])
    m = re.search(r"POINT\(([-\d.]+) ([-\d.]+)\)", p[2])
    if not y or not m:
        continue
    y = int(y.group(1))
    if y in YEARS:
        wdser[p[0]][y] = int(float(p[3]))
        wdlab[p[0]] = re.sub(r'^"|"@en$', "", p[1])
        wdco[p[0]] = (float(m.group(2)), float(m.group(1)))
wd_places = []
for q, s in wdser.items():
    if sum(1 for y in YEARS if y in s) < 8 or s.get(1801) is None:
        continue
    lat, lon = wdco[q]
    ksea = float(ctree.query((lon * KX, lat * KY))[0])
    if ksea < 25 or not (49.8 < lat < 56):
        continue
    ry, sname, sd = rail(lat, lon)
    wd_places.append({"place": wdlab[q], "group": "inland_wikidata", "article": q.strip("<>"), "country": "England", "lat": lat, "lon": lon,
                      "coord_source": "Wikidata", "rail_year": ry, "rail_source": f"Wikidata: earliest opening date of a station within 3 km ({sname})" if ry else "",
                      "rail_year_wikidata_3km": ry, "rail_station": sname, "km_to_sea": round(ksea, 1), "vob_unit": "", "vob_unit_id": "",
                      "url": q.strip("<>"), "mode": "wikidata", "wd": q})
print("Wikidata inland parishes with 8+ census figures, 1801 present, 25 km+ from the sea:", len(wd_places))

# ---------------- 5. populations.csv and intervals.csv
prow, irow = [], []
for pl in places:
    s = pop[pl["place"]]
    for y in YEARS:
        if y in s:
            prow.append({"place": pl["place"], "group": pl["group"], "year": y, "population": s[y][0] if s[y][0] is not None else "",
                         "earlier_same_boundary": s[y][1] if s[y][1] is not None else "",
                         "source": f'A Vision of Britain through Time, {pl["vob_unit"]}', "url": pl["url"]})
        if (pl["place"], y) in EXTRA:
            v, src = EXTRA[(pl["place"], y)]
            prow.append({"place": pl["place"], "group": pl["group"], "year": y, "population": v, "earlier_same_boundary": "", "source": src,
                         "url": "https://en.wikipedia.org/wiki/Blackpool"})
    for y in YEARS[1:]:
        if y not in s or s[y][0] is None:
            continue
        a, kind = None, None
        if s[y][1] is not None:
            a, kind = s[y][1], "same boundary (restated)"
        elif (y - 10) in s and s[y - 10][0] is not None:
            a, kind = s[y - 10][0], "consecutive"
        if a and a > 0 and s[y][0] > 0:
            irow.append({"place": pl["place"], "group": pl["group"], "start": y - 10, "end": y, "pop_start": a, "pop_end": s[y][0],
                         "growth_pct_yr": round(100 * math.log(s[y][0] / a) / 10, 4), "pair": kind})
for pl in wd_places:
    s = wdser[pl["wd"]]
    for y in YEARS:
        if y in s:
            prow.append({"place": pl["place"], "group": pl["group"], "year": y, "population": s[y], "earlier_same_boundary": "",
                         "source": "Wikidata population (P1082) with point in time", "url": pl["url"]})
    for y in YEARS[1:]:
        if y in s and (y - 10) in s and s[y] > 0 and s[y - 10] > 0:
            irow.append({"place": pl["place"], "group": pl["group"], "start": y - 10, "end": y, "pop_start": s[y - 10], "pop_end": s[y],
                         "growth_pct_yr": round(100 * math.log(s[y] / s[y - 10]) / 10, 4), "pair": "consecutive"})

allp = places + wd_places
for pl in allp:
    iv = [i for i in irow if i["place"] == pl["place"] and i["group"] == pl["group"]]
    pl["n_intervals"] = len(iv)
    ry = pl["rail_year"]
    pl["n_before"] = sum(1 for i in iv if ry and i["end"] <= ry)
    pl["n_after"] = sum(1 for i in iv if ry and i["start"] >= ry)
    s = pop.get(pl["place"], {}) if pl["group"] != "inland_wikidata" else {y: (v, None) for y, v in wdser[pl["wd"]].items()}
    pl["pop1801"] = (s.get(1801, (None,))[0]) or EXTRA.get((pl["place"], 1801), (None,))[0]
    pl["pop1851"] = s.get(1851, (None,))[0]
    pl["pop1911"] = s.get(1911, (None,))[0] if pl["group"] != "inland_wikidata" else s.get(1901, (None,))[0]

cols = ["place", "group", "article", "country", "lat", "lon", "coord_source", "km_to_sea", "rail_year", "rail_source", "rail_year_wikidata_3km",
        "vob_unit", "vob_unit_id", "url", "mode", "pop1801", "pop1851", "pop1911", "n_intervals", "n_before", "n_after"]
with open(os.path.join(D, "places.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(allp)
with open(os.path.join(D, "populations.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(prow[0].keys()))
    w.writeheader()
    w.writerows(prow)
with open(os.path.join(D, "intervals.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(irow[0].keys()))
    w.writeheader()
    w.writerows(irow)
json.dump(checks_summary, open(os.path.join(D, "checks.json"), "w"), indent=1)
for g in ("resort", "inland", "inland_wikidata"):
    P = [p for p in allp if p["group"] == g]
    print(g, len(P), "with rail", sum(1 for p in P if p["rail_year"]), "2+ before & 2+ after", sum(1 for p in P if p["n_before"] >= 2 and p["n_after"] >= 2))
print("earlier==previous", agree, "differs", differ)
