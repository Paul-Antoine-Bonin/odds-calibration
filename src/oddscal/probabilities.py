"""Turn decimal odds into raw implied probabilities.

Decimal odds of 4.0 return 4 units for every 1 staked, so the break-even
probability is 1 / 4.0 = 0.25. That reciprocal is the *raw* implied
probability.

Raw is the operative word. Across the three outcomes these probabilities sum to
more than one, and the excess is the bookmaker's margin. Nothing here removes
it: normalisation is a later step, and doing it too early would hide the very
quantity the project is trying to measure.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np
import pandas as pd

from . import sources
from .load import IDENTITY_COLUMNS

OUTCOMES = ("home", "draw", "away")

# Decimal odds of exactly 1.0 pay nothing and below 1.0 are impossible. Both
# appear in the files as data entry errors, and both would produce a probability
# of 1 or more, so they are dropped rather than clipped.
MIN_VALID_ODDS = 1.0


def implied_probability(odds):
    """Raw implied probability of a decimal odds quote, elementwise.

    Invalid quotes (missing, zero, negative, or not above 1.0) give NaN rather
    than a misleading number.
    """
    values = pd.to_numeric(pd.Series(odds), errors="coerce").astype("float64")
    valid = values > MIN_VALID_ODDS
    return pd.Series(np.where(valid, 1.0 / values.where(valid), np.nan),
                     index=values.index)


def to_long_odds(
    matches: pd.DataFrame,
    prefixes: Optional[Sequence[str]] = None,
    kinds: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Reshape the wide match frame to one row per (match, odds source).

    By default only real quotes are kept, so the site's own maximum and mean
    columns are excluded. Pass `kinds` to override.

    Rows where any of the three odds is invalid are dropped: a partial triple
    cannot be normalised later, and keeping it would bias the margin downwards.
    """
    if kinds is None:
        wanted = sources.quote_sources()
    else:
        wanted = [s for s in sources.all_sources() if s.kind in kinds]
    if prefixes is not None:
        wanted = [s for s in wanted if s.prefix in prefixes]

    identity = [c for c in ["match_id"] + IDENTITY_COLUMNS if c in matches.columns]
    pieces: List[pd.DataFrame] = []

    for source in wanted:
        home_col, draw_col, away_col = source.columns
        if not all(col in matches.columns for col in source.columns):
            continue

        piece = matches[identity].copy()
        piece["source"] = source.prefix
        piece["bookmaker"] = source.name
        piece["kind"] = source.kind
        piece["phase"] = source.phase
        piece["odds_home"] = pd.to_numeric(matches[home_col], errors="coerce")
        piece["odds_draw"] = pd.to_numeric(matches[draw_col], errors="coerce")
        piece["odds_away"] = pd.to_numeric(matches[away_col], errors="coerce")

        complete = (
            (piece["odds_home"] > MIN_VALID_ODDS)
            & (piece["odds_draw"] > MIN_VALID_ODDS)
            & (piece["odds_away"] > MIN_VALID_ODDS)
        )
        piece = piece[complete]
        if not piece.empty:
            pieces.append(piece)

    if not pieces:
        return pd.DataFrame(
            columns=identity
            + ["source", "bookmaker", "kind", "phase"]
            + [f"odds_{o}" for o in OUTCOMES]
        )

    return pd.concat(pieces, ignore_index=True, sort=False)


def add_raw_probabilities(long_odds: pd.DataFrame) -> pd.DataFrame:
    """Add `p_raw_home`, `p_raw_draw` and `p_raw_away` to a long odds frame.

    These are reciprocals of the odds and are deliberately left unnormalised.
    """
    out = long_odds.copy()
    for outcome in OUTCOMES:
        out[f"p_raw_{outcome}"] = 1.0 / out[f"odds_{outcome}"]
    return out


def build_raw_probabilities(
    matches: pd.DataFrame,
    prefixes: Optional[Sequence[str]] = None,
    kinds: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Wide match frame to long quotes carrying raw implied probabilities."""
    return add_raw_probabilities(to_long_odds(matches, prefixes=prefixes, kinds=kinds))
