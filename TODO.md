# odds-calibration: are bookmakers well calibrated?

## Goal
Odds imply a probability. If a bookmaker quotes 20% on a thousand matches, about two
hundred should happen. Check that, and measure the margin and the
favourite-longshot bias precisely.

## Data
- football-data.co.uk: free CSVs, several leagues, more than twenty seasons, odds from
  several bookmakers plus results. Ideal source, no key needed.

## Steps
- [x] Set up repo, download script for the CSVs by league and season
- [x] Convert decimal odds into raw implied probabilities
- [x] Compute the overround (the sum exceeds 1), which is the bookmaker's margin
- [ ] Normalise to get clean probabilities, then compare normalisation methods
      (proportional against power)
- [ ] Split into probability buckets and plot the calibration curve
- [ ] Compute the Brier score, overall and per bucket
- [ ] Test the favourite-longshot bias: are longshots systematically overpriced?
- [ ] Compare bookmakers against each other, and by league
- [ ] README: who is best calibrated, and where the margin hides

## Done when
The calibration curve is produced on more than 50,000 matches, with a Brier score and
a clear conclusion on the longshot bias.

## Traps
- Comparing bookmakers on different samples distorts everything. Use only the matches
  both of them priced.
- Encoding is not uniform. Of the 450 files downloaded, 11 are latin-1 rather than
  utf-8 (older German, English and Scottish seasons) and several carry a utf-8 BOM.
  The reader needs a fallback, otherwise those seasons drop out silently.
- The odds columns move around between seasons. Older files carry bookmakers that no
  longer exist (GB, LB, SB), recent ones add Max and Avg columns. Select columns by
  name, never by position.
- Max and Avg are not bookmakers. They are the site's maximum and mean across books,
  so their implied probabilities can sum to less than 1. `to_long_odds` tags them as
  aggregates and drops them by default. Never let them into a calibration curve.
- 20 quotes out of 1.49 million imply probabilities summing below 1, the lowest at
  0.62. These are data entry errors, not arbitrage, and they would drag the measured
  margin down. Filter them when computing the overround.
- The sample trap is not hypothetical, it already bit once. Grouping every quote by
  phase says closing books are 2.9 points tighter than opening ones. Restricted to
  the pairs carrying both, the gap is 0.03 points. The first number is measuring
  which seasons and which bookmakers publish a closing price, nothing else.
- Overround and margin are different numbers and get used interchangeably in the
  literature. B - 1 against (B - 1) / B, roughly 8.0% against 6.9% here. Quote the
  margin: it is the expected loss per unit staked.
