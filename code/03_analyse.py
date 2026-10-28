"""Step 3. Analysis. Writes data/results.json (every number used in the page, paper, blog and collage)
and _site_data.json (compact map and chart data for the page; removed by step 4).

Event time. For a place whose railway arrived in year A, a census interval running from s to s+10 has event time
k = ceil((s - A) / 10): k = 0 is the interval in which the line opened, k = -1 the decade before it, k = 1 the decade
after, and so on. "Before" means k <= -1, "after" k >= 1. Growth is the annual rate 100 x ln(P_end / P_start) / 10.

Groups. Resorts: places on Wikipedia's "List of seaside resorts in the United Kingdom" with census figures.
Inland towns: a seeded random sample of OS Open Names towns 25 km or more from the sea (code/00_inland_sample.py).
Inland parishes (Wikidata): every Wikidata place with eight or more census figures 1801 to 1901, 25 km or more from
the sea (mostly Cambridgeshire, Huntingdonshire, Dorset and Somerset villages); a rough second check only.
"""
import csv
import gzip
import json
import math
import os
import re
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
H = "/home/claude/hist"
R = {}

P = pd.read_csv(os.path.join(D, "places.csv"))
I = pd.read_csv(os.path.join(D, "intervals.csv"))
RS = pd.read_csv(os.path.join(D, "resorts.csv"))
POP = pd.read_csv(os.path.join(D, "populations.csv"))
CHK = json.load(open(os.path.join(D, "checks.json")))
LOG = list(csv.DictReader(open(os.path.join(D, "vob_search_log.tsv"), encoding="utf-8"), delimiter="\t"))
I = I.merge(P[["place", "group", "rail_year"]], on=["place", "group"], how="left")
I = I[I.rail_year.notna()].copy()
I["k"] = np.ceil((I.start - I.rail_year) / 10).astype(int)
I["phase"] = np.where(I.k <= -1, "before", np.where(I.k >= 1, "after", "arrival"))
GROUPS = {"resort": "Seaside resorts", "inland": "Inland towns", "inland_wikidata": "Inland parishes (Wikidata)"}

# ---------------- coverage
places_list = RS[~RS.not_a_place]
R["coverage"] = {
    "list_entries": int(len(RS)),
    "list_not_places": int(RS.not_a_place.sum()),
    "list_places": int(len(places_list)),
    "list_places_gb": int((~places_list.country.fillna("").str.startswith("Northern")).sum()),
    "list_places_ni": int(places_list.country.fillna("").str.startswith("Northern").sum()),
    "with_point": int(places_list.lat.notna().sum()),
    "with_rail_3km": int(places_list.rail_year_3km.notna().sum()),
    "with_rail": int(places_list.rail_year.notna().sum()),
    "no_station_3km": int(places_list.rail_year.isna().sum()),
    "rail_overrides_list": int(places_list.rail_source.fillna("").str.startswith("Wikipedia").sum()),
    "coord_from_osnames": int(places_list.coord_source.str.startswith("OS Open Names").sum()),
    "resorts_with_census": int((P.group == "resort").sum()),
    "resorts_full_1801_1911": int(((P.group == "resort") & P.pop1801.notna() & P.pop1911.notna()).sum()),
    "inland_tried": 60,
    "inland_with_census": int((P.group == "inland").sum()),
    "wikidata_parishes": int((P.group == "inland_wikidata").sum()),
    "wikidata_parishes_with_rail": int(((P.group == "inland_wikidata") & P.rail_year.notna()).sum()),
    "checks_n": CHK["n_checks"], "checks_match": CHK["n_match"],
    "pairs_agree": CHK["pairs_earlier_equals_previous"], "pairs_differ": CHK["pairs_earlier_differs"],
    "rail_overrides_resorts": int((P[P.group == "resort"].rail_source.fillna("").str.startswith("Wikipedia")).sum()),
    "rail_overrides_inland": int((P[P.group == "inland"].rail_source.fillna("").str.startswith("Wikipedia")).sum()),
    "n_population_figures": int(len(POP[POP.group != "inland_wikidata"])),
    "n_intervals_resort": int((I.group == "resort").sum()),
}
for g in GROUPS:
    q = P[P.group == g]
    R["coverage"][f"{g}_event_sample"] = int(((q.n_before >= 2) & (q.n_after >= 2)).sum())

# railway arrival by decade for all resort places with a station within 3 km
rail_all = [int(y) for y in places_list.rail_year.dropna()]
dec = Counter(y // 10 * 10 for y in rail_all)
R["arrival"] = {"n": len(rail_all), "by_decade": [{"decade": d, "n": dec[d]} for d in sorted(dec)],
                "median": float(np.median(rail_all)), "before_1850": sum(1 for y in rail_all if y < 1850),
                "y1840s": sum(1 for y in rail_all if 1840 <= y < 1850), "after_1880": sum(1 for y in rail_all if y >= 1880),
                "earliest": min(rail_all), "latest": max(rail_all), "peak_decade": max(dec, key=dec.get), "peak_n": dec[max(dec, key=dec.get)]}
R["arrival"]["share_by_1860"] = sum(1 for y in rail_all if y < 1860) / len(rail_all)

# ---------------- event study: mean growth by event time
ev = {}
for g in GROUPS:
    q = I[I.group == g]
    rows = []
    for k in range(-6, 8):
        z = q[q.k == k].growth_pct_yr
        if len(z) >= 5:
            rows.append({"k": k, "n": int(len(z)), "mean": float(z.mean()), "median": float(z.median()),
                         "se": float(z.std(ddof=1) / math.sqrt(len(z)))})
    ev[g] = rows
R["event"] = ev


def phase_means(df):
    out = {}
    for ph in ("before", "arrival", "after"):
        z = df[df.phase == ph].growth_pct_yr
        out[ph] = {"n": int(len(z)), "mean": float(z.mean()) if len(z) else None, "median": float(z.median()) if len(z) else None}
    return out


R["phases"] = {g: phase_means(I[I.group == g]) for g in GROUPS}

# ---------------- per place: up to three decades before vs up to three decades after
pp = []
for (pl, g), q in I.groupby(["place", "group"]):
    b = q[q.k.isin([-3, -2, -1])].growth_pct_yr
    a = q[q.k.isin([1, 2, 3])].growth_pct_yr
    if len(b) >= 1 and len(a) >= 1:
        pp.append({"place": pl, "group": g, "before": float(b.mean()), "after": float(a.mean()), "change": float(a.mean() - b.mean()),
                   "rail_year": int(q.rail_year.iloc[0]), "nb": int(len(b)), "na": int(len(a))})
PP = pd.DataFrame(pp)
R["per_place"] = {}
for g in GROUPS:
    q = PP[PP.group == g]
    R["per_place"][g] = {"n": int(len(q)), "median_before": float(q.before.median()), "median_after": float(q.after.median()),
                         "median_change": float(q.change.median()), "mean_change": float(q.change.mean()),
                         "n_faster_after": int((q.change > 0).sum()), "share_faster_after": float((q.change > 0).mean()),
                         "wilcoxon_p": float(stats.wilcoxon(q.change).pvalue) if len(q) >= 6 else None}
mw = stats.mannwhitneyu(PP[PP.group == "resort"].change, PP[PP.group == "inland"].change)
R["per_place"]["mw_resort_vs_inland_p"] = float(mw.pvalue)
mw2 = stats.mannwhitneyu(PP[PP.group == "resort"].change, PP[PP.group == "inland_wikidata"].change)
R["per_place"]["mw_resort_vs_wikidata_p"] = float(mw2.pvalue)
R["per_place"]["resort_rows"] = [{"place": r.place, "before": round(r.before, 2), "after": round(r.after, 2), "change": round(r.change, 2),
                                  "rail_year": r.rail_year} for r in PP[PP.group == "resort"].sort_values("change", ascending=False).itertuples()]

# ---------------- regression: place and period fixed effects, after-railway indicator, resort interaction
X = I[I.group.isin(["resort", "inland"])].copy()
X["after"] = (X.k >= 1).astype(int)
X["arrival"] = (X.k == 0).astype(int)
X["resort"] = (X.group == "resort").astype(int)
X["pid"] = X.group + ":" + X.place
m = smf.ols("growth_pct_yr ~ C(pid) + C(start) + after + arrival + after:resort + arrival:resort", data=X).fit(
    cov_type="cluster", cov_kwds={"groups": pd.factorize(X.pid)[0]})


def term(mm, t):
    ci = mm.conf_int().loc[t]
    return {"coef": float(mm.params[t]), "lo": float(ci[0]), "hi": float(ci[1]), "p": float(mm.pvalues[t])}


R["reg"] = {"n_obs": int(m.nobs), "n_places": int(X.pid.nunique()), "after_inland": term(m, "after"), "after_x_resort": term(m, "after:resort"),
            "arrival_inland": term(m, "arrival"), "arrival_x_resort": term(m, "arrival:resort")}
# resorts alone
Xr = X[X.resort == 1]
mr = smf.ols("growth_pct_yr ~ C(pid) + C(start) + after + arrival", data=Xr).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(Xr.pid)[0]})
R["reg"]["resort_only_after"] = term(mr, "after")
R["reg"]["resort_only_arrival"] = term(mr, "arrival")
R["reg"]["resort_only_n"] = int(mr.nobs)
# event-time dummies for resorts (k binned at -4 and +5, reference k = -1)
Xr = Xr.copy()
Xr["kb"] = Xr.k.clip(-4, 5)
me = smf.ols("growth_pct_yr ~ C(pid) + C(start) + C(kb, Treatment(reference=-1))", data=Xr).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(Xr.pid)[0]})
R["reg"]["resort_event"] = []
for k in range(-4, 6):
    if k == -1:
        R["reg"]["resort_event"].append({"k": k, "coef": 0.0, "lo": 0.0, "hi": 0.0})
        continue
    t = f"C(kb, Treatment(reference=-1))[T.{k}]"
    if t in me.params:
        R["reg"]["resort_event"].append({"k": k, **{kk: v for kk, v in term(me, t).items() if kk != "p"}, "p": float(me.pvalues[t])})
# with Wikidata parishes as the comparison
X2 = I[I.group.isin(["resort", "inland_wikidata"])].copy()
X2["after"] = (X2.k >= 1).astype(int)
X2["arrival"] = (X2.k == 0).astype(int)
X2["resort"] = (X2.group == "resort").astype(int)
X2["pid"] = X2.group + ":" + X2.place
m2 = smf.ols("growth_pct_yr ~ C(pid) + C(start) + after + arrival + after:resort + arrival:resort", data=X2).fit(
    cov_type="cluster", cov_kwds={"groups": pd.factorize(X2.pid)[0]})
R["reg"]["wd_after_inland"] = term(m2, "after")
R["reg"]["wd_after_x_resort"] = term(m2, "after:resort")

# ---------------- before any railway: growth 1801 to 1831
pre = []
Iall = pd.read_csv(os.path.join(D, "intervals.csv"))
for (pl, g), q in Iall.groupby(["place", "group"]):
    q = q.set_index("start")
    if all(s in q.index for s in (1801, 1811, 1821)):
        pre.append({"place": pl, "group": g, "g0131": float(q.loc[[1801, 1811, 1821], "growth_pct_yr"].mean())})
PRE = pd.DataFrame(pre)
R["pre1831"] = {}
for g in GROUPS:
    z = PRE[PRE.group == g].g0131
    R["pre1831"][g] = {"n": int(len(z)), "median": float(z.median()), "mean": float(z.mean()),
                       "share_above_1pct": float((z > 1).mean()), "q75": float(z.quantile(.75))}
R["pre1831"]["mw_resort_inland_p"] = float(stats.mannwhitneyu(PRE[PRE.group == "resort"].g0131, PRE[PRE.group == "inland"].g0131).pvalue)
R["pre1831"]["mw_resort_wd_p"] = float(stats.mannwhitneyu(PRE[PRE.group == "resort"].g0131, PRE[PRE.group == "inland_wikidata"].g0131).pvalue)
# doubling time equivalents
for g in GROUPS:
    r_ = R["pre1831"][g]["median"] / 100
    R["pre1831"][g]["growth_30yr"] = float(math.exp(r_ * 30))
R["pre1831"]["fastest_resorts"] = [{"place": r.place, "g": round(r.g0131, 2)} for r in PRE[PRE.group == "resort"].sort_values("g0131", ascending=False).head(8).itertuples()]

# ---------------- size-matched comparison: resorts vs inland towns of similar 1801 size
pm = P[P.pop1801.notna() & P.group.isin(["resort", "inland"])].copy()
pm["lp"] = np.log(pm.pop1801)
pairs = []
inl = pm[pm.group == "inland"]
for r in pm[pm.group == "resort"].itertuples():
    j = (inl.lp - r.lp).abs().idxmin()
    pairs.append((r.place, inl.loc[j, "place"], abs(inl.loc[j, "lp"] - r.lp)))
R["matched"] = {"n_pairs": len(pairs), "median_log_gap": float(np.median([p[2] for p in pairs]))}
# Long-run growth chained over same-boundary decades: 1801 to 1851 and 1871 to 1911 (nine decades). 1851 to 1871 is left
# out for every place because the England and Wales parish tables cannot pair it on one boundary. Published 1801 and 1911
# figures are kept for display only, because boundaries changed between them (Whitby, Hunstanton, Bakewell).
CH_STARTS = [1801, 1811, 1821, 1831, 1841, 1871, 1881, 1891, 1901]
ch = []
for (pl, g), q in Iall[Iall.group.isin(["resort", "inland"])].groupby(["place", "group"]):
    q = q.set_index("start")
    if all(s_ in q.index for s_ in CH_STARTS):
        ch.append({"place": pl, "group": g, "chain": float(math.exp(q.loc[CH_STARTS, "growth_pct_yr"].sum() / 10))})
CH = pd.DataFrame(ch)
pm = pm.merge(CH, on=["place", "group"], how="left")
pm["mult"] = pm.pop1911 / pm.pop1801
both = pm[pm.chain.notna()]
R["long"] = {"decades": "1801 to 1851 and 1871 to 1911"}
for g in ("resort", "inland"):
    z = both[both.group == g].chain
    R["long"][g] = {"n": int(len(z)), "median_mult": float(z.median()), "share_3x": float((z >= 3).mean()), "n_3x": int((z >= 3).sum())}
inl2 = both[both.group == "inland"]
mp = []
for r in both[both.group == "resort"].itertuples():
    j = (inl2.lp - r.lp).abs().idxmin()
    mp.append((r.place, inl2.loc[j, "place"], r.chain, inl2.loc[j, "chain"]))
R["matched"] = {"n_with_1911": len(mp), "resort_bigger_growth": sum(1 for x in mp if x[2] > x[3]),
                "median_ratio": float(np.median([x[2] / x[3] for x in mp])),
                "median_log_gap": float(np.median([abs(both[both.place == a].lp.iloc[0] - both[both.place == b].lp.iloc[0]) for a, b, _, _ in mp]))}
R["matched"]["sign_p"] = float(stats.binomtest(R["matched"]["resort_bigger_growth"], len(mp)).pvalue)
R["matched"]["pairs"] = [{"resort": a, "inland": b, "resort_mult": round(x, 2), "inland_mult": round(y, 2)} for a, b, x, y in mp]
R["long"]["mw_p"] = float(stats.mannwhitneyu(both[both.group == "resort"].chain, both[both.group == "inland"].chain).pvalue)
R["long"]["top_resorts"] = [{"place": r.place, "pop1801": int(r.pop1801), "pop1911": int(r.pop1911), "chain": round(r.chain, 1)}
                            for r in both[both.group == "resort"].sort_values("chain", ascending=False).head(10).itertuples()]
R["long"]["published"] = {r.place: {"pop1801": int(r.pop1801), "pop1911": int(r.pop1911), "mult": round(r.mult, 1)}
                          for r in pm[(pm.group == "resort") & pm.mult.notna()].itertuples()}

# ---------------- types: small places in 1801 (built from almost nothing) vs established towns
rs = P[(P.group == "resort") & P.pop1801.notna()].copy()
rs = rs.merge(PP[PP.group == "resort"][["place", "before", "after", "change"]], on="place", how="left")
rs["small1801"] = rs.pop1801 < 1000
R["types"] = {}
for lab, q in [("small", rs[rs.small1801]), ("established", rs[~rs.small1801])]:
    qq = q[q.change.notna()]
    R["types"][lab] = {"n": int(len(q)), "n_change": int(len(qq)), "median_change": float(qq.change.median()),
                       "median_before": float(qq.before.median()), "median_after": float(qq.after.median()),
                       "share_faster_after": float((qq.change > 0).mean()),
                       "places": q.sort_values("pop1801").place.tolist()}

# ---------------- case studies (figures straight from the census series)
def series(pl):
    q = POP[(POP.place == pl)].sort_values("year")
    return [{"year": int(r.year), "pop": int(r.population)} for r in q.itertuples() if not pd.isna(r.population) and r.population != ""]


CASES = ["Blackpool", "Skegness", "Weston-super-Mare", "Brighton", "Torquay", "Llandudno", "Frinton-on-Sea", "Margate", "Scarborough", "Bexhill-on-Sea",
         "Southend-on-Sea", "Eastbourne", "Whitby", "Cromer", "Lytham St Annes", "Clevedon", "Walton-on-the-Naze"]
R["cases"] = {}
for c in CASES:
    s = series(c)
    q = PP[(PP.place == c) & (PP.group == "resort")]
    R["cases"][c] = {"rail_year": int(P[(P.place == c) & (P.group == "resort")].rail_year.iloc[0]), "series": s,
                     "before": float(q.before.iloc[0]) if len(q) else None, "after": float(q.after.iloc[0]) if len(q) else None}

# ---------------- distance from the big industrial towns vs arrival year (England and Wales)
TL = json.load(open(f"{H}/_data9/wikipedia_wikitext.json", encoding="utf-8"))["List of towns and cities in England by historical population"]["text"]
tab = [t for t in re.findall(r"\{\|(.*?)\n\|\}", TL, re.S) if re.search(r"\|\+\s*1861", t)][0]
big = []
for row in re.sub(r"<ref.*?(</ref>|/>)", "", tab, flags=re.S).split("\n|-"):
    mm = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]\s*\|\|\s*([\d,]+)", row)
    if mm:
        big.append(((mm.group(2) or mm.group(1)).split(",")[0].strip(), int(mm.group(3).replace(",", ""))))
big = big[:10]
osn = {}
with open(f"{H}/osnames_gb.tsv", encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["type"] == "populatedPlace" and r["local_type"] in ("City", "Town") and r["country"] == "England":
            osn.setdefault(r["name1"], (float(r["lat"]), float(r["lon"])))
BIGPT = {}
for nm, pp_ in big:
    key = {"Newcastle": "Newcastle upon Tyne", "Stoke-upon-Trent": "Stoke-on-Trent"}.get(nm, nm)
    if key in osn:
        BIGPT[nm] = osn[key]
R["cities"] = {"names": [n for n, _ in big], "placed": list(BIGPT.keys()), "pops1861": {n: p for n, p in big}}


def km(a, b):
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((a[1] - b[1]) * 111.32 * k, (a[0] - b[0]) * 110.57)


dist_rows = []
for r in places_list.itertuples():
    if r.country not in ("England", "Wales") or pd.isna(r.lat):
        continue
    y = None if pd.isna(r.rail_year) else int(r.rail_year)
    d = min(km((r.lat, r.lon), v) for v in BIGPT.values())
    nb = min(BIGPT, key=lambda n: km((r.lat, r.lon), BIGPT[n]))
    dist_rows.append({"place": r.list_name, "rail_year": y, "km_big": d, "nearest_big": nb, "km_london": km((r.lat, r.lon), BIGPT["London"])})
DR = pd.DataFrame(dist_rows)
DRr = DR[DR.rail_year.notna()]
rho, p = stats.spearmanr(DRr.km_big, DRr.rail_year)
rho2, p2 = stats.spearmanr(DRr.km_london, DRr.rail_year)
bands = [(0, 50), (50, 100), (100, 150), (150, 400)]
R["distance"] = {"n": int(len(DRr)), "n_no_rail": int(DR.rail_year.isna().sum()), "spearman": float(rho), "p": float(p),
                 "spearman_london": float(rho2), "p_london": float(p2),
                 "bands": [{"lo": lo, "hi": hi, "n": int(((DRr.km_big >= lo) & (DRr.km_big < hi)).sum()),
                            "median_year": int(math.floor(DRr[(DRr.km_big >= lo) & (DRr.km_big < hi)].rail_year.median() + 0.5))} for lo, hi in bands]}
R["distance"]["no_rail_median_km"] = float(DR[DR.rail_year.isna()].km_big.median())
R["distance"]["rail_median_km"] = float(DRr.km_big.median())

# ---------------- headline helpers
rr = R["per_place"]["resort"]
ii = R["per_place"]["inland"]
R["head"] = {"resort_before": rr["median_before"], "resort_after": rr["median_after"], "inland_before": ii["median_before"], "inland_after": ii["median_after"],
             "resort_change": rr["median_change"], "inland_change": ii["median_change"],
             "resort_n": rr["n"], "inland_n": ii["n"], "pre_resort": R["pre1831"]["resort"]["median"], "pre_inland": R["pre1831"]["inland"]["median"],
             "pre_wd": R["pre1831"]["inland_wikidata"]["median"], "extra_after": R["reg"]["after_x_resort"]["coef"]}

json.dump(R, open(os.path.join(D, "results.json"), "w"), indent=1)

# ---------------- site data
site = {"resorts": [], "series": {}, "pp": R["per_place"]["resort_rows"]}
pmap = {r.place: r for r in P[P.group == "resort"].itertuples()}
ppm = {r.place: r for r in PP[PP.group == "resort"].itertuples()}
for r in places_list.itertuples():
    if pd.isna(r.lat):
        continue
    y = None if pd.isna(r.rail_year) else int(r.rail_year)
    q = pmap.get(r.list_name)
    e = ppm.get(r.list_name)
    site["resorts"].append([r.list_name, round(r.lat, 4), round(r.lon, 4), y,
                            int(q.pop1801) if q is not None and not pd.isna(q.pop1801) else None,
                            int(q.pop1911) if q is not None and not pd.isna(q.pop1911) else None,
                            round(e.before, 2) if e is not None else None, round(e.after, 2) if e is not None else None,
                            r.rail_station if isinstance(r.rail_station, str) else "", r.title if isinstance(r.title, str) else ""])
for pl in P[P.group.isin(["resort", "inland"])].itertuples():
    s = POP[(POP.place == pl.place) & (POP.group == pl.group)].sort_values("year")
    site["series"][f"{pl.group}:{pl.place}"] = [[int(x.year), int(x.population)] for x in s.itertuples() if not pd.isna(x.population)]
site["pre"] = [[r.place, r.group, round(r.g0131, 3)] for r in PRE.itertuples()]
site["inland"] = [[r.place, round(r.lat, 4), round(r.lon, 4), int(r.rail_year)] for r in P[P.group == "inland"].itertuples()]
json.dump(site, open(os.path.join(ROOT, "_site_data.json"), "w"), separators=(",", ":"))

print(json.dumps(R["head"], indent=1))
print("phases", json.dumps(R["phases"], indent=0)[:900])
print("reg", {k: (round(v["coef"], 2), round(v["p"], 3)) for k, v in R["reg"].items() if isinstance(v, dict) and "coef" in v})
print("pre1831", {g: (R["pre1831"][g]["n"], round(R["pre1831"][g]["median"], 2)) for g in GROUPS}, R["pre1831"]["mw_resort_inland_p"])
print("per_place", {g: (R["per_place"][g]["n"], round(R["per_place"][g]["share_faster_after"], 2), R["per_place"][g]["wilcoxon_p"]) for g in GROUPS}, R["per_place"]["mw_resort_vs_inland_p"])
print("long", R["long"], "matched", R["matched"])
print("types", {k: (v["n"], v["n_change"], round(v["median_change"], 2), round(v["share_faster_after"], 2)) for k, v in R["types"].items()})
print("distance", R["distance"])
print("arrival", R["arrival"])
print("event resort", [(e["k"], e["n"], round(e["mean"], 2)) for e in R["event"]["resort"]])
print("event inland", [(e["k"], e["n"], round(e["mean"], 2)) for e in R["event"]["inland"]])
print("resort event reg", [(e["k"], round(e["coef"], 2)) for e in R["reg"]["resort_event"]])
print("coverage", R["coverage"])
