"""Split normalised probabilities into buckets and draw the calibration curve.

The question the project exists to answer has one natural shape. Take every
probability a bookmaker quoted, group the quotes that said roughly the same
thing, and count how often the thing happened. A bucket around 20% should
contain outcomes that occurred about 20% of the time. Plot the observed
frequency against the quoted probability and a perfectly calibrated book sits
on the diagonal.

Two decisions carry the module.

**One quote becomes three observations.** A 1X2 quote is three probabilities
and exactly one of them occurred. Stacking home, draw and away into a single
column of (probability, occurred) pairs is what makes a bucket mean "every
outcome the book priced near p", whichever outcome it happened to be. The
alternative, one row per match, would answer a narrower question about home
wins only. The three observations from a quote are not independent, and
`bucket_calibration` does not pretend otherwise: the interval it reports is a
binomial one and it is optimistic by roughly the amount that dependence costs.

**The bucket edges are a choice.** Equal-width buckets are the honest default
because they are fixed in advance and do not move with the sample, but the
archive is heavily concentrated between 0.15 and 0.6, so the extreme buckets
end up thin. `QUANTILE_BUCKETS` gives equal-count buckets instead, which is the
right shape for reading the longshot end where the interesting claim lives.
Neither is more correct; both are reported, and a curve without its bucket
counts beside it is not readable.

The interval is Wilson rather than the normal approximation. At an observed
frequency near 0.02 on a few hundred observations the normal interval reaches
below zero, which is not a statement about football.

Nothing here scores the forecasts: that is the Brier score, step 6. This module
only says where the curve sits.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

from .normalise import NORMALISED_COLUMNS, normalise
from .probabilities import OUTCOMES

# The result letter in the archive, per outcome column.
RESULT_LETTERS = {"home": "H", "draw": "D", "away": "A"}

# Fixed edges, 5 percentage points wide, plus a first and last bucket cut finer:
# almost nothing sits above 0.9 and the longshot end is where the bias claim is.
EQUAL_WIDTH_BUCKETS = (
    [0.0, 0.02, 0.05]
    + [round(0.05 * i, 2) for i in range(2, 19)]
    + [0.95, 1.0]
)

# Equal-count buckets, given as quantiles rather than edges.
QUANTILE_BUCKETS = 20

# Wilson interval at 95%.
_Z = 1.959963984540054


def to_observations(
    quotes: pd.DataFrame,
    method: Optional[str] = None,
    keep: Sequence[str] = ("bookmaker", "season", "division", "kind"),
) -> pd.DataFrame:
    """One row per (quote, outcome), carrying the probability and whether it happened.

    `quotes` must already carry `p_home`, `p_draw`, `p_away`, or `method` must
    name a normalisation to apply first. Naming the method matters: the two
    methods disagree by a fifth of the probability on the longest shots, so a
    calibration curve without its method attached says nothing.

    Rows with a missing probability or an unreadable result are dropped.
    """
    if method is not None:
        quotes = normalise(quotes, method)

    missing = [c for c in NORMALISED_COLUMNS if c not in quotes.columns]
    if missing:
        raise KeyError(
            f"missing normalised columns {missing}; run normalise first "
            "or pass method="
        )
    if "result" not in quotes.columns:
        raise KeyError("missing 'result' column; observations need the match outcome")

    carried = [c for c in keep if c in quotes.columns]
    result = quotes["result"].astype(str).str.strip().str.upper()

    frames = []
    for outcome in OUTCOMES:
        piece = quotes[carried].copy()
        piece["outcome"] = outcome
        piece["p"] = quotes[f"p_{outcome}"].to_numpy(dtype=float)
        piece["occurred"] = (result == RESULT_LETTERS[outcome]).to_numpy()
        frames.append(piece)

    stacked = pd.concat(frames, ignore_index=True)
    # A result outside H/D/A never matches a letter, so all three of its rows
    # would silently count as "did not occur". Drop the quote instead.
    readable = pd.concat(
        [result.isin(RESULT_LETTERS.values())] * len(OUTCOMES), ignore_index=True
    )
    stacked = stacked[readable & stacked["p"].between(0.0, 1.0)]
    return stacked.reset_index(drop=True)


def wilson_interval(successes, total, z: float = _Z):
    """Wilson score interval for a binomial proportion, elementwise.

    Chosen over the normal approximation because the buckets at both ends carry
    frequencies close to 0 and 1, where the normal interval leaves the unit
    square and stops meaning anything.
    """
    successes = np.asarray(successes, dtype=float)
    total = np.asarray(total, dtype=float)

    with np.errstate(invalid="ignore", divide="ignore"):
        p = successes / total
        denominator = 1.0 + z * z / total
        centre = (p + z * z / (2.0 * total)) / denominator
        spread = (
            z
            * np.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total))
            / denominator
        )
    low = np.where(total > 0, np.clip(centre - spread, 0.0, 1.0), np.nan)
    high = np.where(total > 0, np.clip(centre + spread, 0.0, 1.0), np.nan)
    return low, high


def bucket_calibration(
    observations: pd.DataFrame,
    bins=EQUAL_WIDTH_BUCKETS,
    by: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Observed frequency against mean quoted probability, one row per bucket.

    `bins` takes either a sequence of edges or an integer, in which case the
    buckets are equal-count quantiles of the observed probabilities.

    Columns: `observations`, `occurred`, `p_mean`, `frequency`, `ci_low`,
    `ci_high`, and `gap` = frequency - p_mean. A negative gap means the outcome
    happened less often than the price implied, so that bucket was overpriced.
    """
    for column in ("p", "occurred"):
        if column not in observations.columns:
            raise KeyError(f"missing '{column}' column; run to_observations first")

    frame = observations.dropna(subset=["p"]).copy()
    if isinstance(bins, int):
        frame["bucket"] = pd.qcut(frame["p"], q=bins, duplicates="drop")
    else:
        # include_lowest so a probability of exactly 0 is not dropped.
        frame["bucket"] = pd.cut(frame["p"], bins=list(bins), include_lowest=True)

    keys = list(by) + ["bucket"] if by else ["bucket"]
    grouped = frame.groupby(keys, observed=True).agg(
        observations=("occurred", "size"),
        occurred=("occurred", "sum"),
        p_mean=("p", "mean"),
    )
    grouped["occurred"] = grouped["occurred"].astype(int)
    grouped["frequency"] = grouped["occurred"] / grouped["observations"]
    low, high = wilson_interval(grouped["occurred"], grouped["observations"])
    grouped["ci_low"] = low
    grouped["ci_high"] = high
    grouped["gap"] = grouped["frequency"] - grouped["p_mean"]
    return grouped.reset_index()


def calibration_summary(table: pd.DataFrame) -> pd.Series:
    """Three numbers describing how far a calibration table sits off the diagonal.

    `mean_absolute_gap` weights each bucket by its size, so a thin extreme
    bucket cannot dominate. `buckets_off_diagonal` counts the buckets whose
    Wilson interval excludes their own mean probability, which is the
    bucket-level version of the question and the one that survives a large
    sample making every gap significant.
    """
    weights = table["observations"]
    total = weights.sum()
    off = ~table["p_mean"].between(table["ci_low"], table["ci_high"])
    return pd.Series(
        {
            "buckets": len(table),
            "observations": int(total),
            "mean_absolute_gap": float(
                np.average(table["gap"].abs(), weights=weights)
            ) if total else np.nan,
            "weighted_gap": float(np.average(table["gap"], weights=weights))
            if total
            else np.nan,
            "buckets_off_diagonal": int(off.sum()),
        }
    )


def plot_calibration(
    tables,
    path=None,
    title: str = "Calibration of bookmaker odds",
    log_x: bool = False,
):
    """Draw the calibration curve, or several on the same axes.

    `tables` is one table from `bucket_calibration` or a mapping
    {label: table}. Returns the matplotlib figure. If `path` is given the
    figure is written there.

    The bucket counts go underneath as a bar panel. A calibration curve read
    without them invites conclusions from buckets holding two hundred
    observations out of four million.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if isinstance(tables, pd.DataFrame):
        tables = {"quoted": tables}

    figure, (axes, counts) = plt.subplots(
        2,
        1,
        figsize=(7.5, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
    )

    axes.plot([0, 1], [0, 1], color="0.6", linewidth=1, linestyle="--",
              label="perfect calibration")

    for label, table in tables.items():
        table = table.sort_values("p_mean")
        line, = axes.plot(
            table["p_mean"],
            table["frequency"],
            marker="o",
            markersize=4,
            linewidth=1.2,
            label=label,
        )
        # vlines rather than errorbar: the Wilson interval is not centred on
        # the observed frequency, so at the extreme buckets one arm would come
        # out negative and errorbar refuses it. The interval is what it is.
        axes.vlines(
            table["p_mean"],
            table["ci_low"],
            table["ci_high"],
            color=line.get_color(),
            linewidth=1.0,
        )
        counts.plot(table["p_mean"], table["observations"], marker=".", linewidth=1,
                    label=label)

    axes.set_ylabel("observed frequency")
    axes.set_title(title)
    axes.legend(loc="upper left", frameon=False)
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)

    counts.set_yscale("log")
    counts.set_ylabel("observations")
    counts.set_xlabel("quoted probability")
    if log_x:
        axes.set_xscale("log")
        counts.set_xscale("log")

    if path is not None:
        figure.savefig(path, dpi=150, bbox_inches="tight")
    return figure
