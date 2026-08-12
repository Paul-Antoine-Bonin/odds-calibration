# odds-calibration

Are bookmakers well calibrated?

Odds imply a probability. If a bookmaker quotes 20% on a thousand matches, about two
hundred should happen. This repo checks that against twenty-five seasons of football
results, and measures where the margin sits.

No calibration results yet. Data collection and the conversion to raw implied
probabilities both work.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Get the data

```bash
python -m oddscal.download                      # 18 leagues, seasons 2000/01 to 2024/25
python -m oddscal.download --leagues E0 --from 2020 --to 2024   # a smaller slice
```

Files land in `data/raw/<season>/<league>.csv`, which is git-ignored. Reruns are
cached, so only missing files are fetched. A league that did not run in a given season
returns 404, which counts as missing rather than as a failure.

## Use it

```python
from oddscal.load import load_matches
from oddscal.probabilities import build_raw_probabilities

matches = load_matches()                    # one row per match
quotes = build_raw_probabilities(matches)   # one row per (match, bookmaker)
```

`quotes` carries `odds_home/draw/away` and the reciprocals `p_raw_home/draw/away`.
Raw means unnormalised: the three add up to more than 1, and that excess is the
margin. Removing it is the next step, and doing it here would hide the quantity the
project is trying to measure.

## What the source actually contains

Measured on the full default league set, seasons 2000/01 to 2024/25:

| | |
|---|---|
| Files downloaded | 450 of 450, no failures |
| Size on disk | 45.1 MiB |
| Matches with a result | 166,628 |
| Seasons, divisions | 25, 18 |
| Date range | 2000-07-28 to 2025-06-01 |
| Dates that failed to parse | 0 |
| Distinct 1X2 odds triples | 31 |
| Quotes, match by source | 1,491,529 |
| Home / draw / away | 74,856 / 44,798 / 46,974 |

That clears the 50,000 match target in the roadmap with room to spare. Loading the
whole archive takes about 30 seconds.

Four quirks in the archive, all handled in `load.py` and `sources.py`:

- 11 of the 450 files are latin-1 rather than utf-8, and several carry a utf-8 BOM
- the Greek files from 2000 to 2005 name the teams `HT` and `AT`
- most files end in a block of blank filler rows, and some rows are short
- `Max`, `Avg` and the older `BbMx`, `BbAv` are the site's maximum and mean across
  bookmakers, not quotes anyone offered. They are tagged as aggregates and excluded
  by default

One sanity check on the conversion: 99.9987% of the 1.49 million quotes imply
probabilities summing above 1, as they must. The 20 that do not are data entry errors
in the source, the worst being 8.00 / 3.75 / 4.33 on Rimini against Juventus in
2006, which sums to 0.62.

## Run the tests

```bash
pytest
```

Roadmap and progress: [TODO.md](TODO.md)
