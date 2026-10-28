# Did the railway invent the seaside?

Did Britain's seaside resorts boom after the railway arrived, or were they already growing? Census figures for 68 resorts, 1801 to 1911, lined up against the year their first station opened, and compared with a random sample of inland towns.

**Interactive version:** https://tristan-hotham.github.io/seaside-railways/

**Paper:** https://doi.org/10.5281/zenodo.23727127

This repository holds the interactive page, the datasets, the computed results and the analysis code for a data study by Dr Tristan Hotham (Independent researcher).

## Headline results

- Of the 205 places on Wikipedia's List of seaside resorts in the United Kingdom, 177 had a railway station within 3 km by 1911. The busiest decade was the 1840s, when 51 resorts got their first station; half had one by 1861.
- Resorts near the big industrial towns got the railway first: within 50 km of one of the ten largest English towns of 1861 the median arrival year was 1849; more than 150 km away, 1878 (Spearman rank correlation 0.23, 159 resorts in England and Wales, p = 0.003).
- Before any railway (1801 to 1831) the typical resort grew 1.63% a year (52 resorts), against 1.43% for a random sample of inland towns (20 towns; Mann-Whitney p = 0.34) and 1.09% for 280 inland villages with Wikidata census figures.
- With resort and census-decade fixed effects, resort growth was 1.33 points a year higher in the decade the railway arrived than in the decade before (95% interval 0.24 to 2.42), and 1.18 points higher in the decade after (-0.06 to 2.43). Decades before the railway show no build-up.
- That lift is not clearly special to the seaside: in a joint model, the resorts' extra after-railway growth over inland towns was 0.08 points a year (95% interval -1.20 to 1.36).
- 26 of 43 resorts grew faster in the three census decades after their railway than in the three before; 6 of 15 inland towns did (Mann-Whitney p = 0.07). The biggest gains were at Frinton, Eastbourne, Southend, Seaford and Skegness; the resorts that boomed before the railway (Weston-super-Mare, Torquay, Brighton, Clevedon, Ramsgate) slowed after it.
- Over the nine census decades that can be compared on the same boundaries (1801 to 1851 and 1871 to 1911), the typical resort multiplied 3.9 times (40 resorts) and the typical inland town 3.0 times (15 towns; Mann-Whitney p = 0.42). In 27 of 40 pairs matched on 1801 population the resort grew more (sign test p = 0.04).

These are associations, not causes: railways were built where promoters expected traffic.

## Files

- `index.html`: the interactive page (map with a year slider, charts, "find your resort"). Data embedded; works as a single file.
- `header.png`: social card (1200 by 630).
- `data/resorts.csv`: every entry on the Wikipedia list (218), with its point and where it came from, the railway year (`rail_year`) and its source (`rail_source`: the Wikidata station, or the quoted sentence from the resort's article where that was used), the Wikidata year within 1, 3 and 5 km, and the railway sentence found in the resort article.
- `data/vob_transcriptions.tsv`: every census figure collected, exactly as read from A Vision of Britain through Time, with the unit name, unit id and page URL.
- `data/vob_search_log.tsv`: resorts and sampled inland towns that were looked up but not used, and why.
- `data/populations.csv`: one row per place and census year (resorts, inland towns and the Wikidata inland villages), with source and URL.
- `data/intervals.csv`: every ten-year growth interval used, with start and end population and how the pair was formed.
- `data/places.csv`: one row per analysed place: point, distance to the sea, railway year and source, census unit.
- `data/inland_sample.csv`: the 60 randomly sampled inland towns, in sampled order.
- `data/checks.json`: transcriptions checked against figures quoted on Wikipedia (5 of 5 match) and a consistency count.
- `data/results.json`: every number quoted on the page, in the paper, the blog post and the collage.
- `code/00_inland_sample.py`: draws the inland town sample (seed 1801).
- `code/vob_add.py`: helper used to record each Vision of Britain page as it was read.
- `code/01_resorts.py`: parses the resort list, places each resort and dates its railway.
- `code/02_populations.py`: builds the population series and growth intervals, checks the transcriptions, adds railway dates for inland places.
- `code/03_analyse.py`: event study, regressions, comparisons; writes `results.json` and a temporary page data file.
- `code/04_build_page.py`: fills `code/page_template.html` from `results.json` to make `index.html`.
- `code/05_header.py`: renders `header.png` with Playwright.
- `release/`: the paper (PDF, LaTeX source and figures), the blog post and figures, and the Zenodo files.
- `reddit/`: the collage and its script.

## How to rerun

The scripts read the source files in place (paths at the top of each script): the Wikipedia and Wikidata bundles retrieved on 27 and 28 October 2026, OS Open Names and the Natural Earth coastline. The census figures are in `data/vob_transcriptions.tsv`; they were collected by hand-directed web lookups and cannot be re-downloaded by the scripts.

```
python3 code/01_resorts.py
python3 code/02_populations.py
python3 code/03_analyse.py
python3 code/04_build_page.py
python3 code/05_header.py [font_dir]
```

It needs Python 3 with pandas, numpy, scipy, statsmodels and playwright.

## Method in brief

- Railway year: the earliest Wikidata opening date (P1619) of any station within 3 km of the resort's point. Where the resort's own Wikipedia article gives an earlier arrival (7 resorts, such as Blackpool 1846, where Wikidata gives 1974 for Blackpool North), the article's year is used and quoted. Five inland towns were corrected the same way from their station articles.
- Long-run growth: chained same-boundary decades 1801 to 1851 and 1871 to 1911, so that boundary changes (for example at Whitby and Hunstanton) do not show up as growth or loss.
- Census figures: total population of the resort's census parish or township at each census from 1801 to 1911, from the "Total Population" (or "Males and Females") pages of A Vision of Britain through Time. Blackpool's 1801 figure (473) is from its Wikipedia article.
- Growth: annual rate 100 x ln(P_end / P_start) / 10, where P_start is the figure for ten years earlier restated on the same boundary when the census gives one. For England and Wales the parish tables have no 1861 figure, and 1851 to 1871 is not bridged.
- Event time: a census decade starting in year s has event time ceil((s - A) / 10), where A is the railway year; 0 is the decade in which the line opened.
- Comparisons: a random sample (seed 1801) of 60 OS Open Names towns at least 25 km from the sea, of which 20 had usable census series; and 288 Wikidata places with eight or more census figures 1801 to 1901 at least 25 km from the sea.

## Known limits

- Coverage: 68 of the 201 resorts in Great Britain have census series (50 with both 1801 and 1911); 45 have two or more decades both before and after the railway. Suburb resorts, resorts split across parishes and parishes created late are missing, so the sample leans to England and to separate parishes. Northern Ireland has no series here.
- The figures were read from web pages with an automated reader. All five that could be checked against Wikipedia matched, and each figure is linked to its page, but errors are possible.
- Parishes are not towns. Boundaries changed; same-boundary pairs are used for each decade where printed, and long-run growth is chained over those pairs; the published 1801 and 1911 figures quoted for single towns are on different boundaries.
- A station within 3 km is not the same as a good service into the town centre, and Wikidata dates may still hold some rebuilding dates.
- The inland sample is small (20 towns), and the Wikidata villages are mostly in Cambridgeshire, Huntingdonshire, Dorset and Somerset.

## Sources and licences

- Census populations 1801 to 1911: published census reports for England and Wales and for Scotland, as tabulated by A Vision of Britain through Time, University of Portsmouth, https://www.visionofbritain.org.uk/ (each figure linked to its page).
- Resort list, resort articles and the 1861 town ranking: Wikipedia, "List of seaside resorts in the United Kingdom", the linked resort articles, and "List of towns and cities in England by historical population", CC BY-SA 4.0, retrieved 27 and 28 October 2026. Station dates for five inland towns: the Wikipedia articles on Loughborough, Berkhamsted, Leighton Buzzard, Evesham and Llanfair Caereinion railway stations.
- Wikidata (station opening dates, village census figures): CC0.
- OS Open Names: contains OS data © Crown copyright and database right 2026; Open Government Licence v3.0.
- Coastline: Natural Earth, public domain. Base map tiles: Esri.

The data in `data/` and the text of the page are released under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/), because they derive from Wikipedia. The code (`code/`) is released under the MIT licence (see `LICENSE`).

## Citation

Hotham, T. (2026). Did the Railway Invent the Seaside? Census Growth of British Resorts Before and After the Line Arrived, 1801 to 1911. Zenodo. https://doi.org/10.5281/zenodo.23727127

I wrote the text, with drafting and editing assistance from Claude (Anthropic), which also helped prepare the analysis code. I reviewed and checked all text and results.
