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
- [x] Normalise to get clean probabilities, then compare normalisation methods
      (proportional against power)
- [x] Split into probability buckets and plot the calibration curve
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
- Normalising is an assumption, not a cleanup. Proportional and power give different
  probabilities for the same quote, and the gap is large where it matters: on the
  archive the power method assigns 20.9% less probability to outcomes under 0.1, and
  4.6% more to outcomes above 0.7. Any calibration result has to name the method it
  used, and the favourite-longshot test in particular will move with it.
- The power exponent has to be solved per quote, not assumed. Median k is 1.0781 across
  the archive and the middle 80% spans 1.0315 to 1.1330. Bisection, not Newton: the
  sum is monotone in k so a bracket always converges, and a guaranteed answer on 1.5
  million rows beats a faster one that can diverge.
- The sample trap is not hypothetical, it already bit once. Grouping every quote by
  phase says closing books are 2.9 points tighter than opening ones. Restricted to
  the pairs carrying both, the gap is 0.03 points. The first number is measuring
  which seasons and which bookmakers publish a closing price, nothing else.
- Overround and margin are different numbers and get used interchangeably in the
  literature. B - 1 against (B - 1) / B, roughly 8.0% against 6.9% here. Quote the
  margin: it is the expected loss per unit staked.
- One quote is three observations, not one. Stacking home, draw and away is what
  makes a bucket mean "every outcome priced near p". They are not independent, so
  the Wilson interval on a bucket is optimistic by roughly what that dependence
  costs. On 4.4 million observations that hardly matters for the shape of the
  curve, but it does mean "18 of 20 buckets off the diagonal" is a weaker
  statement than it looks.
- Wilson, not the normal approximation, and not errorbar. The interval is not
  centred on the observed frequency, so at the extreme buckets one arm points the
  wrong way and matplotlib's errorbar refuses negative values outright. Drawing
  the interval as it actually sits is the fix; clipping it would have been a lie
  at exactly the buckets the longshot claim depends on.
- Equal-width and equal-count buckets answer different questions. The archive
  piles up between 0.15 and 0.6, so an equal-width bucket above 0.9 holds 565
  observations against 1.27 million in the modal one. Never show the curve
  without the counts underneath.
