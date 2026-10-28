"""Step 0. Draw the inland comparison towns (run once, before collecting census figures).

Every OS Open Names "Town" point in England and Wales at least 25 km from the Natural Earth coastline, de-duplicated,
sorted, then a random sample of 60 with Python's random.seed(1801). Census figures were then looked up for the towns
in sampled order; the towns found are in data/vob_transcriptions.tsv (group "inland") and the misses in
data/vob_search_log.tsv.

Reads: osnames_gb.tsv (OGL v3), _data3/ne/geojson/ne_10m_coastline.geojson (public domain)
Writes: data/inland_sample.csv
"""
import csv
import json
import math
import os
import random

import numpy as np
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = "/home/claude/hist"
KX, KY = 111.32 * math.cos(math.radians(53)), 110.57
coast = []
for ft in json.load(open(f"{H}/_data3/ne/geojson/ne_10m_coastline.geojson"))["features"]:
    g = ft["geometry"]
    for ln in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]):
        if any(-8 < x < 2.5 and 49.5 < y < 59 for x, y in ln):
            coast += ln
t = cKDTree(np.array([(x * KX, y * KY) for x, y in coast]))
towns = []
for r in csv.DictReader(open(f"{H}/osnames_gb.tsv", encoding="utf-8"), delimiter="\t"):
    if r["type"] == "populatedPlace" and r["local_type"] == "Town" and r["country"] in ("England", "Wales"):
        d = t.query((float(r["lon"]) * KX, float(r["lat"]) * KY))[0]
        if d >= 25:
            towns.append((r["name1"], r["county"] or r["district"], r["lat"], r["lon"], round(d, 1)))
print("eligible towns", len(towns))
random.seed(1801)
s = random.sample(sorted(set(towns)), 60)
with open(os.path.join(ROOT, "data", "inland_sample.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["order", "town", "county_or_district", "lat", "lon", "km_to_sea"])
    for i, x in enumerate(s, 1):
        w.writerow([i, *x])
