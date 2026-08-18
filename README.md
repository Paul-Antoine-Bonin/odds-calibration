# odds-calibration

Are bookmakers well calibrated?

Odds imply a probability. If a bookmaker quotes 20% on a thousand matches, about two
hundred should happen. This repo checks that against twenty-five seasons of football
results, and measures where the margin sits.

No calibration results yet. Data collection, the conversion to raw implied
probabilities and the margin are all in place: across 1.47 million bookmaker quotes
the median book keeps **6.94%** of turnover, and that figure has roughly halved
since 2000.

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
from oddscal.overround import add_overround, summarise_overround

matches = load_matches()                    # one row per match
quotes = build_raw_probabilities(matches)   # one row per (match, bookmaker)
quotes = add_overround(quotes)              # booksum, overround, margin

summarise_overround(quotes, by=["bookmaker"])
```

`quotes` carries `odds_home/draw/away` and the reciprocals `p_raw_home/draw/away`.
Raw means unnormalised: the three add up to more than 1, and that excess is the
margin. Normalising is the next step, and doing it earlier would hide the quantity
the project is trying to measure.

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
probabilities summing above 1, as they must. The 20 that do not are handled below.

## The margin

The three raw probabilities sum to the *booksum* B. Two numbers come out of it and
they are not the same:

| | | on this archive |
|---|---|---|
| overround | B - 1 | 7.98% mean |
| margin | (B - 1) / B | 6.94% median, 7.29% mean |

The margin is the one worth quoting. Normalise proportionally, take the result as
true, and a unit staked on any of the three outcomes returns `1/B - 1 = -(B-1)/B`.
Every outcome carries the same expected loss, and it equals the margin.

Measured on 1,465,200 bookmaker quotes, excluding the exchange and the aggregates.
The middle 80% of books sit between 3.02% and 11.11%.

### Who charges what

Median margin per bookmaker, over whatever the archive holds for each:

| Bookmaker | Quotes | Median margin |
|---|---|---|
| Pinnacle | 172,005 | 2.73% |
| 1XBet | 13,015 | 4.82% |
| VC Bet | 159,006 | 5.41% |
| Bet365 | 191,782 | 6.02% |
| Bet&Win | 174,174 | 7.03% |
| William Hill | 194,356 | 7.36% |
| Stan James | 60,563 | 7.87% |
| Blue Square | 39,758 | 8.62% |
| Gamebookers | 83,519 | 9.24% |
| Sportingbet | 75,040 | 9.39% |
| Interwetten | 183,587 | 9.41% |
| Sporting Odds | 6,575 | 10.33% |
| Ladbrokes | 106,776 | 10.56% |
| Stanleybet | 5,044 | 10.83% |

Pinnacle at a quarter of Stanleybet's margin is the known result and it survives
here. But this table is not a fair ranking: these are different samples, different
leagues and different decades. The honest comparison comes at step 8, on the matches
the books priced in common.

### The margin has halved, and it is not a composition effect

Grouping every quote by season shows the median falling from 11.4% in 2000/01 to
5.3% in 2024/25. That could just be Pinnacle arriving late and dragging the average
down, so the same curve held to a single bookmaker throughout:

| Bookmaker | First season | Last season |
|---|---|---|
| William Hill | 11.21% (2000/01) | 6.09% (2024/25) |
| Interwetten | 14.92% (2000/01) | 5.76% (2023/24) |
| Bet365 | 10.92% (2002/03) | 5.97% (2024/25) |

The decline is real, roughly a halving inside each book, but the three do not get
there the same way. William Hill sits flat near 11% until 2008/09 then drops to 6.5%
within two seasons; Bet365 makes the same jump in one, 8.5% to 6.3% between 2007/08
and 2008/09. Interwetten has no step at all and grinds down across the whole period.
A shared cause would be worth a look, though nothing here establishes one.

### Two comparisons that mostly measure the sample

- **Opening against closing.** Grouped naively, closing quotes look 2.9 points
  tighter (4.95% against 7.82%). Restricted to the 267,565 (match, bookmaker) pairs
  carrying both, the median difference is 0.03 points, and closing is tighter in
  53.6% of pairs. The naive gap was measuring which seasons publish a closing price.
- **Exchange against bookmakers.** On the 6,589 matches priced by both, Betfair's
  median booksum implies 4.59% against 5.29% for the bookmakers. The gap is real but
  the numbers are not comparable: the exchange takes commission on winnings rather
  than pricing its cut into the quote.

By division the spread is narrower than by bookmaker: the Premier League is tightest
at 5.69% and the Spanish second division widest at 8.30%, with the other sixteen in
between. Top flights are cheaper than the divisions below them, everywhere.

### The 20 bad books

`drop_implausible_books` removes the quotes whose booksum is at or below 1. There are
20 in 1.49 million, the worst being 8.00 / 3.75 / 4.33 on Rimini against Juventus in
2006, which sums to 0.62. They are typing errors in the archive rather than
arbitrage. Dropping them is the right thing to do and it changes the headline margin
by less than 0.0001 points, which is the answer this filter deserved.

## Run the tests

```bash
pytest
```

Roadmap and progress: [TODO.md](TODO.md)
