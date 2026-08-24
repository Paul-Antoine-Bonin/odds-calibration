"""Turn raw implied probabilities into probabilities that sum to 1.

The three reciprocals sum to the booksum B > 1. Removing that excess is not a
single operation: it is an assumption about *where* the bookmaker put the
margin, and different assumptions give different probabilities for the same
quote.

Two methods, as the roadmap asks:

**Proportional.** Divide each raw probability by B.

    p_i = p_raw_i / B

Every outcome is shaded by the same factor, so the margin is assumed
proportional to the probability. This is the standard choice and the one that
makes the expected loss identical across the three outcomes, which is why
`overround.py` quotes the margin the way it does.

**Power.** Raise each raw probability to a common exponent k chosen so the
three sum to 1.

    p_i = p_raw_i ** k,   with k solving  sum_i p_raw_i ** k = 1

Because every raw probability is below 1 and their sum exceeds 1, the solution
has k > 1, and raising to a power above 1 shrinks small numbers proportionally
harder than large ones. So the power method takes more margin out of the
longshot than out of the favourite. That is the whole point: it encodes the
belief that the favourite-longshot bias is real and that the bookmaker loads
its cut onto the outsider.

Which of the two is better calibrated is not decided here. It needs the
calibration curve and the Brier score, which are steps 5 and 6 of the roadmap.
What this module gives is the two candidate sets of probabilities and an
honest measure of how far apart they are.

The exponent is found by bisection rather than Newton. `sum_i p^k` is strictly
decreasing in k, so a bracket that straddles the root always converges, and a
guaranteed answer on 1.5 million rows is worth more than a faster one that can
diverge on a degenerate quote.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from .probabilities import OUTCOMES

RAW_COLUMNS = [f"p_raw_{outcome}" for outcome in OUTCOMES]
NORMALISED_COLUMNS = [f"p_{outcome}" for outcome in OUTCOMES]

METHODS = ("proportional", "power")

# The exponent lies above 1 for any overrounding book. The bracket is generous
# at both ends so that a book summing below 1, which the archive does contain,
# still solves rather than silently pinning to the boundary.
_K_LOW = 0.05
_K_HIGH = 30.0

# 60 halvings of a 30 wide bracket resolve k to about 2.6e-17, past float64
# precision, and cost nothing on vectorised data.
_BISECTION_STEPS = 60


def _require_raw(quotes: pd.DataFrame) -> np.ndarray:
    missing = [c for c in RAW_COLUMNS if c not in quotes.columns]
    if missing:
        raise KeyError(
            f"missing raw probability columns {missing}; "
            "run probabilities.add_raw_probabilities first"
        )
    return quotes[RAW_COLUMNS].to_numpy(dtype=float)


def solve_power_exponent(raw: np.ndarray) -> np.ndarray:
    """The exponent k that makes each row of raw probabilities sum to 1.

    `raw` is (n, 3). Returns (n,). Rows containing a value outside (0, 1), or
    any NaN, return NaN rather than a number that would look usable.
    """
    raw = np.asarray(raw, dtype=float)
    if raw.ndim != 2 or raw.shape[1] != len(OUTCOMES):
        raise ValueError(f"expected an (n, {len(OUTCOMES)}) array, got {raw.shape}")

    usable = np.all(np.isfinite(raw) & (raw > 0.0) & (raw < 1.0), axis=1)

    low = np.full(raw.shape[0], _K_LOW)
    high = np.full(raw.shape[0], _K_HIGH)

    for _ in range(_BISECTION_STEPS):
        mid = 0.5 * (low + high)
        # sum(p ** k) is strictly decreasing in k for 0 < p < 1.
        total = np.sum(raw ** mid[:, None], axis=1)
        too_high = total > 1.0
        low = np.where(too_high, mid, low)
        high = np.where(too_high, high, mid)

    k = 0.5 * (low + high)
    return np.where(usable, k, np.nan)


def normalise(quotes: pd.DataFrame, method: str = "proportional") -> pd.DataFrame:
    """Add `p_home`, `p_draw`, `p_away` normalised by the chosen method.

    The raw columns are kept: the margin is computed from them, and a later
    step comparing methods needs both.
    """
    if method not in METHODS:
        raise ValueError(
            f"unknown method {method!r}, expected one of {', '.join(METHODS)}"
        )

    raw = _require_raw(quotes)
    out = quotes.copy()

    if method == "proportional":
        total = raw.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            normalised = raw / total[:, None]
    else:
        k = solve_power_exponent(raw)
        out["power_k"] = k
        with np.errstate(invalid="ignore"):
            normalised = raw ** k[:, None]

    for column, values in zip(NORMALISED_COLUMNS, normalised.T):
        out[column] = values
    return out


def normalisation_error(quotes: pd.DataFrame) -> pd.Series:
    """How far each normalised triple is from summing to exactly 1.

    A check, not a statistic. Proportional is exact to floating point by
    construction; power is exact only to the tolerance of the solver, and this
    is what says whether that tolerance is good enough.
    """
    missing = [c for c in NORMALISED_COLUMNS if c not in quotes.columns]
    if missing:
        raise KeyError(f"missing normalised columns {missing}; run normalise first")
    return quotes[NORMALISED_COLUMNS].sum(axis=1, skipna=False) - 1.0


def compare_methods(quotes: pd.DataFrame) -> pd.DataFrame:
    """Both normalisations side by side, one row per quote.

    Returns the identity columns plus `p_<outcome>_proportional`,
    `p_<outcome>_power`, the solved `power_k`, and the signed difference
    `power - proportional` for each outcome.

    The sign is the interesting part. Where the difference is negative the
    power method assigns a lower probability than the proportional one, which
    is what it should do to a longshot.
    """
    proportional = normalise(quotes, "proportional")
    power = normalise(quotes, "power")

    keep = [c for c in quotes.columns if not c.startswith("p_raw_")]
    out = quotes[keep].copy()
    out["power_k"] = power["power_k"]

    for outcome in OUTCOMES:
        column = f"p_{outcome}"
        out[f"{column}_proportional"] = proportional[column]
        out[f"{column}_power"] = power[column]
        out[f"{column}_diff"] = power[column] - proportional[column]
    return out


def difference_by_probability_bucket(
    quotes: pd.DataFrame, bins: Sequence[float] = (0.0, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0)
) -> pd.DataFrame:
    """Mean gap between the two methods, by proportional probability bucket.

    Reshapes the three outcomes into one column of probabilities so a bucket
    holds every quote of that strength, whichever outcome it happened to be.
    This is the shape that shows whether the power method really is doing
    something different at the longshot end.
    """
    comparison = compare_methods(quotes)

    frames = []
    for outcome in OUTCOMES:
        frames.append(
            pd.DataFrame(
                {
                    "p_proportional": comparison[f"p_{outcome}_proportional"],
                    "p_power": comparison[f"p_{outcome}_power"],
                    "difference": comparison[f"p_{outcome}_diff"],
                }
            )
        )
    stacked = pd.concat(frames, ignore_index=True).dropna()

    stacked["bucket"] = pd.cut(stacked["p_proportional"], bins=list(bins))
    grouped = stacked.groupby("bucket", observed=True).agg(
        quotes=("difference", "size"),
        mean_proportional=("p_proportional", "mean"),
        mean_power=("p_power", "mean"),
        mean_difference=("difference", "mean"),
    )
    grouped["relative_difference"] = (
        grouped["mean_difference"] / grouped["mean_proportional"]
    )
    return grouped.reset_index()
