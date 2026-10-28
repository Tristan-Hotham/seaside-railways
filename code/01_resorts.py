"""Step 1. Resorts: the Wikipedia list, a point for each resort, and the year the railway arrived.

Reads (in place, never copied):
  _data11/wikipedia_batch11.json.gz   "List of seaside resorts in the United Kingdom" and the linked resort
                                      articles (English Wikipedia, CC BY-SA 4.0, retrieved 28 October 2026)
  _data11/wd_osm_bundle11.json.gz     wd_stations: Wikidata railway stations in the UK with opening dates (CC0)
  osnames_gb.tsv                      OS Open Names (OGL v3), fallback points

Writes:
  data/resorts.csv   one row per resort place on the list: article, country, point and where the point came from,
                     railway arrival year (earliest opening date of any Wikidata station within 3 km, with the
                     station named), the same within 1 km and 5 km, and the sentence in the resort's own article
                     that mentions the railway arriving (when one is found) as a cross-check.

Railway arrival: the earliest Wikidata opening date (P1619) among stations within RADIUS_KM of the resort point.
Stations without an opening date cannot count. Heritage and later stations do not matter, because the earliest is taken.
"""
import csv
import gzip
import json
import math
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = "/home/claude/hist"
OUT = os.path.join(ROOT, "data")
RADIUS_KM = 3.0

W = json.load(gzip.open(f"{H}/_data11/wikipedia_batch11.json.gz"))["articles"]
LIST = W["List of seaside resorts in the United Kingdom"]["text"].split("== See also")[0]

# Entries on the list that are not a single place (a stretch of coast, a beach, a peninsula, a whole country)
NOT_A_PLACE = {"United Kingdom", "English Riviera", "Gower Peninsula", "The Sunrise Coast", "Camber Sands",
               "Shell Island (Wales)", "Dawlish Warren", "Widemouth Bay", "Trebarwith Strand", "Clarach Bay", "Mwnt",
               "Sandbanks", "Ynyslas", "Crimdon"}

entries = []
seen = set()
for line in LIST.split("\n"):
    if not line.strip().startswith("*"):
        continue
    links = re.findall(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]", line)
    if not links:
        nm = line.strip("* ").strip()
        if nm and nm not in seen:  # unlinked entries (Hayle, Porthleven)
            entries.append({"list_name": nm, "article": "", "linked": False})
            seen.add(nm)
        continue
    target, lab = links[0]
    if target in seen:
        continue
    seen.add(target)
    entries.append({"list_name": (lab or target).split(",")[0].strip(), "article": target, "linked": True})


def dms(parts):
    """Parse the numeric arguments of a {{coord}} template into (lat, lon)."""
    p = [x.strip() for x in parts if x.strip() != ""]
    if len(p) >= 2 and all(re.fullmatch(r"-?\d+(\.\d+)?", x) for x in p[:2]) and (len(p) == 2 or not re.fullmatch(r"[NS]", p[2])) \
            and not (len(p) > 2 and re.fullmatch(r"\d+(\.\d+)?", p[2])):
        return float(p[0]), float(p[1])
    # degrees, minutes, seconds with hemisphere letters
    vals, out, cur = [], [], []
    for x in p:
        if re.fullmatch(r"[NSEW]", x):
            v = sum(float(c) / 60 ** i for i, c in enumerate(cur))
            out.append(-v if x in "SW" else v)
            cur = []
        elif re.fullmatch(r"-?\d+(\.\d+)?", x):
            cur.append(x)
        else:
            break
    if len(out) >= 2:
        return out[0], out[1]
    return None


def coord_from_text(t):
    m = re.search(r"\|\s*coordinates\s*=\s*\{\{\s*[Cc]oord\s*\|([^}]*)\}\}", t) or re.search(r"\{\{\s*[Cc]oord\s*\|([^}]*display\s*=[^}]*title[^}]*)\}\}", t)
    if not m:
        return None
    parts = [x for x in m.group(1).split("|") if "=" not in x and not x.strip().startswith(("region", "type", "scale", "dim"))]
    return dms(parts)


def field(t, name):
    m = re.search(r"\|\s*" + name + r"\s*=\s*([^\n]*)", t)
    if not m:
        return ""
    v = re.sub(r"<ref.*?(</ref>|/>)", "", m.group(1))
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)
    return re.sub(r"\{\{.*?\}\}", "", v).strip()


# OS Open Names fallback (Great Britain only)
osn = defaultdict(list)
with open(f"{H}/osnames_gb.tsv", encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["type"] == "populatedPlace":
            osn[r["name1"]].append(r)

rows = []
for e in entries:
    a = W.get(e["article"]) if e["article"] else None
    t = (a or {}).get("text") or ""
    r = dict(e)
    r["title"] = (a or {}).get("title", "")
    r["wikidata"] = (a or {}).get("wd", "")
    r["country"] = field(t, "country") if t else ""
    r["county"] = field(t, "shire_county") or field(t, "unitary_england") or field(t, "unitary_wales") or field(t, "council_area") \
        or field(t, "lieutenancy_england") or field(t, "lieutenancy_scotland") or field(t, "county") if t else ""
    r["not_a_place"] = e["article"] in NOT_A_PLACE
    lat = lon = None
    src = ""
    if a and a.get("coord"):
        lat, lon, src = a["coord"]["lat"], a["coord"]["lon"], "Wikipedia article coordinates (API)"
    elif t:
        c = coord_from_text(t)
        if c:
            lat, lon, src = c[0], c[1], "Wikipedia article {{coord}} template"
    if lat is None:
        nm = e["list_name"]
        c = osn.get(nm, [])
        hint = r["county"] or ("Cornwall" if nm in ("Hayle", "Porthleven") else "")
        if hint:
            c = [x for x in c if hint.split()[0] in (x["county"] + x["district"] + x["region"])] or c
        c = sorted(c, key=lambda x: {"City": 0, "Town": 1, "Village": 2}.get(x["local_type"], 3))
        if c:
            lat, lon, src = float(c[0]["lat"]), float(c[0]["lon"]), f'OS Open Names ({c[0]["name1"]}, {c[0]["local_type"]}, {c[0]["district"] or c[0]["county"]})'
            if not r["country"]:
                r["country"] = c[0]["country"]
    if lat is not None and not r["country"]:
        # country from the nearest OS Open Names populated place (Great Britain); points west of 5.5 W and north of 54 N
        # with no GB place within 30 km are in Northern Ireland
        best = min(((abs(float(x["lat"]) - lat) + abs(float(x["lon"]) - lon), x["country"]) for v in [osn.get(e["list_name"], [])] for x in v), default=None)
        if best and best[0] < 0.3:
            r["country"] = best[1]
        elif not r["not_a_place"]:  # name not in OS Open Names (e.g. Welsh-first names): nearest populated place
            best = min(((abs(float(x["lat"]) - lat) + abs(float(x["lon"]) - lon), x["country"]) for v in osn.values() for x in v))
            if best[0] < 0.1:
                r["country"] = best[1]
    r["lat"], r["lon"], r["coord_source"] = lat, lon, src
    # article sentences about the railway arriving, for cross-checking
    snips = []
    for m in re.finditer(r"[^.\n]*\b(railway|railways|station|line)\b[^.\n]*\b(18[2-9]\d|19[01]\d)\b[^.\n]*", re.sub(r"<ref.*?(</ref>|/>)", "", t, flags=re.S)):
        s = m.group(0)
        if re.search(r"arriv|open|reach|came|coming|connect|extend|built", s, re.I) and not re.search(r"\b(pier|tram|cliff|miniature|switchback|power|police|fire|lifeboat|pumping)\b", s, re.I):
            s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s).strip(" |'")
            if len(s) < 400 and "File:" not in s and "http" not in s:
                snips.append(s)
    r["article_railway_text"] = snips[0] if snips else ""
    yrs = [int(y) for s in snips for y in re.findall(r"\b(18[2-9]\d|190\d)\b", s)]
    r["article_railway_year_min"] = min(yrs) if yrs else ""
    rows.append(r)

# ---------------- Wikidata stations
B = json.load(gzip.open(f"{H}/_data11/wd_osm_bundle11.json.gz"))["results"]
st = {}
for line in B["wd_stations"]["tsv"].split("\n")[1:]:
    p = line.split("\t")
    if len(p) < 5 or not p[3]:
        continue
    m = re.search(r"POINT\(([-\d.]+) ([-\d.]+)\)", p[2])
    y = re.match(r"(\d{4})", p[3])
    if not m or not y:
        continue
    q = p[0].rsplit("/", 1)[-1].rstrip(">")
    yr = int(y.group(1))
    lab = re.sub(r'^"|"@en$', "", p[1])
    if q not in st or yr < st[q][3]:
        st[q] = (lab, float(m.group(1)), float(m.group(2)), yr)
print("Wikidata stations with an opening year:", len(st))
S = list(st.items())


def km(lat1, lon1, lat2, lon2):
    k = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lon1 - lon2) * 111.32 * k, (lat1 - lat2) * 110.57)


for r in rows:
    if r["lat"] is None:
        continue
    near = sorted(((km(r["lat"], r["lon"], la, lo), y, lab, q) for q, (lab, lo, la, y) in S), key=lambda x: x[0])
    for rad in (1.0, RADIUS_KM, 5.0):
        c = [x for x in near if x[0] <= rad]
        best = min(c, key=lambda x: (x[1], x[0])) if c else None
        tag = {1.0: "1km", RADIUS_KM: "3km", 5.0: "5km"}[rad]
        r[f"rail_year_{tag}"] = best[1] if best else ""
        if rad == RADIUS_KM:
            r["rail_station"] = best[2] if best else ""
            r["rail_station_qid"] = best[3] if best else ""
            r["rail_station_km"] = round(best[0], 2) if best else ""
            r["n_stations_3km"] = len(c)
    r["nearest_station_km"] = round(near[0][0], 2)
    r["nearest_station"] = near[0][2]

# Overrides: where the resort's own Wikipedia article dates the railway's arrival differently from the earliest
# Wikidata station within 3 km (usually because Wikidata holds a rebuilding date). The quoted text must appear in the
# article (links and references stripped).
OVERRIDE = {
    "Blackpool": (1846, "Blackpool", "The opening of a railway station in 1846 allowed more visitors to reach the resort"),
    "Brighton": (1841, "Brighton", "following the arrival of the railways in 1841"),
    "Clevedon": (1847, "Clevedon", "The railway reached Clevedon in 1847"),
    "Aberdyfi": (1863, "Aberdyfi", "The railway came to the village in 1863"),
    "Whitby": (1839, "Whitby", "developed with the arrival of the railway in 1839"),
    "Marazion": (1852, "Marazion", "The West Cornwall Railway opened Marazion railway station on 11 March 1852"),
    "Southend-on-Sea": (1856, "Southend-on-Sea", "the new railway line that opened in 1856"),
}


def plain(t):
    t = re.sub(r"<ref.*?(</ref>|/>)", "", t, flags=re.S)
    return re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)


for r in rows:
    y = r.get("rail_year_3km")
    r["rail_year"] = y if y != "" else ""
    r["rail_source"] = f'Wikidata: earliest opening date of a station within 3 km ({r["rail_station"]}, {r["rail_station_qid"]})' if y else ""
    if r["list_name"] in OVERRIDE:
        oy, art, txt = OVERRIDE[r["list_name"]]
        assert txt in plain(W[art]["text"]), r["list_name"]
        r["rail_year"] = oy
        r["rail_source"] = f'Wikipedia article "{art}": "{txt}"'

cols = ["list_name", "article", "title", "wikidata", "country", "county", "not_a_place", "lat", "lon", "coord_source",
        "rail_year", "rail_source", "rail_year_3km", "rail_station", "rail_station_qid", "rail_station_km", "n_stations_3km", "rail_year_1km", "rail_year_5km",
        "nearest_station", "nearest_station_km", "article_railway_year_min", "article_railway_text"]
with open(os.path.join(OUT, "resorts.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
print("resorts", len(rows), "with point", sum(1 for r in rows if r["lat"] is not None),
      "with rail year (3 km)", sum(1 for r in rows if r.get("rail_year_3km")))
for nm in ["Blackpool", "Brighton", "Skegness", "Bournemouth", "Scarborough", "Margate", "Cleethorpes", "Saltburn-by-the-Sea", "Llandudno"]:
    for r in rows:
        if r["list_name"] == nm:
            print(nm, r.get("rail_year_3km"), r.get("rail_station"), r.get("rail_station_km"), "| article:", r["article_railway_year_min"])
