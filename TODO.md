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
- [ ] Convert decimal odds into raw implied probabilities
- [ ] Compute the overround (the sum exceeds 1), which is the bookmaker's margin
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
