"""Measure the bookmaker's margin from the raw implied probabilities.

Three raw probabilities that summed to exactly 1 would describe a fair book. They
never do. Their sum is the *booksum*, and everything here follows from it:

    booksum   B = 1/o_home + 1/o_draw + 1/o_away
    overround     B - 1        the excess over a fair book
    margin        (B - 1) / B  the share of turnover the bookmaker keeps

The two are routinely confused, and they are not the same number. A book at
B = 1.10 has an overround of 10% but a margin of 9.09%. The margin is the one
with a meaning for the punter: normalise the raw probabilities proportionally,
take them as true, and a unit staked on outcome i returns

    (p_raw_i / B) * o_i - 1 = 1 / B - 1 = -(B - 1) / B

whichever outcome is picked. The expected loss is the margin, identical across
the three, which is why the margin and not the overround is the number to quote.

Two cautions carried by the data itself:

- A handful of quotes sum to less than 1. Those are typing errors in the archive,
  not free money, and averaging them in drags the measured margin down. They are
  dropped by `drop_implausible_books`, which the summary applies by default.
- Betfair is an exchange. Its cut is a commission on winnings, not something
  priced into the quote, so its booksum sits far below a bookmaker's and the two
  are not comparable. Filter on `kind` before reading anything into a ranking.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import pandas as pd

from .probabilities import OUTCOMES

RAW_PROBABILITY_COLUMNS = [f"p_raw_{outcome}" for outcome in OUTCOMES]

# A book that sums to less than 1 offers a guaranteed profit to the punter. At
# the scale of a whole archive these are data entry errors rather than arbitrage,
# so the plausible range starts just above a fair book.
MIN_PLAUSIBLE_BOOKSUM = 1.0


def booksum(quotes: pd.DataFrame) -> pd.Series:
    """Sum of the three raw implied probabilities, one value per quote."""
    missing = [c for c in RAW_PROBABILITY_COLUMNS if c not in quotes.columns]
    if missing:
        raise KeyError(
            f"missing raw probability columns {missing}; "
            "run probabilities.add_raw_probabilities first"
        )
    # skipna=False on purpose: a missing leg summed as a zero would look like an
    # unusually tight book rather than the incomplete quote it is.
    return quotes[RAW_PROBABILITY_COLUMNS].sum(axis=1, skipna=False)


def add_overround(quotes: pd.DataFrame) -> pd.DataFrame:
    """Add `booksum`, `overround` and `margin` to a frame of raw probabilities.

    Nothing is filtered here. Implausible books stay in so that they can be
    counted before being dropped.
    """
    out = quotes.copy()
    out["booksum"] = booksum(out)
    out["overround"] = out["booksum"] - 1.0
    out["margin"] = out["overround"] / out["booksum"]
    return out


def implausible_books(quotes: pd.DataFrame) -> pd.DataFrame:
    """The quotes whose booksum is at or below 1, for inspection."""
    with_overround = quotes if "booksum" in quotes.columns else add_overround(quotes)
    return with_overround[with_overround["booksum"] <= MIN_PLAUSIBLE_BOOKSUM]


def drop_implausible_books(quotes: pd.DataFrame) -> pd.DataFrame:
    """Keep only the quotes that overround, which is all but a few in the archive."""
    with_overround = quotes if "booksum" in quotes.columns else add_overround(quotes)
    return with_overround[with_overround["booksum"] > MIN_PLAUSIBLE_BOOKSUM]


# The median is the headline: a few extreme books at long odds pull the mean up,
# and the deciles say how much the margin moves within a group.
_AGGREGATIONS = {
    "quotes": ("margin", "size"),
    "margin_mean": ("margin", "mean"),
    "margin_median": ("margin", "median"),
    "margin_p10": ("margin", lambda s: s.quantile(0.10)),
    "margin_p90": ("margin", lambda s: s.quantile(0.90)),
    "overround_mean": ("overround", "mean"),
}

_WHOLE_FRAME = "group"


def summarise_overround(
    quotes: pd.DataFrame,
    by: Optional[Sequence[str]] = None,
    drop_implausible: bool = True,
) -> pd.DataFrame:
    """Margin and overround per group, sorted from the tightest book outwards.

    `by` takes any columns of the frame, typically `["bookmaker"]`,
    `["division"]` or `["season"]`. With `by=None` the whole frame is one group.

    The groups are not comparable on their own: bookmakers cover different
    leagues and different eras, so a book that looks tight may simply have
    arrived late and priced only the top divisions. Step 8 of the roadmap
    restricts to a shared sample; this function does not.
    """
    frame = quotes if "margin" in quotes.columns else add_overround(quotes)
    if drop_implausible:
        frame = drop_implausible_books(frame)

    keys: List[str] = list(by) if by is not None else [_WHOLE_FRAME]
    if by is None:
        frame = frame.assign(**{_WHOLE_FRAME: "all"})

    summary = frame.groupby(keys, dropna=False, observed=True).agg(**_AGGREGATIONS)
    summary["quotes"] = summary["quotes"].astype(int)
    return summary.sort_values("margin_median")
