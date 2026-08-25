"""Tests for the buckets and the calibration curve."""

import numpy as np
import pandas as pd
import pytest

from oddscal.calibration import (
    EQUAL_WIDTH_BUCKETS,
    bucket_calibration,
    calibration_summary,
    plot_calibration,
    to_observations,
    wilson_interval,
)


def quotes(n=3):
    """n identical quotes, results cycling through H, D, A."""
    results = ["H", "D", "A"]
    rows = []
    for i in range(n):
        rows.append(
            {
                "match_id": i,
                "bookmaker": "Bet365",
                "kind": "bookmaker",
                "season": "2023/24",
                "result": results[i % 3],
                "odds_home": 2.0, "odds_draw": 4.0, "odds_away": 4.0,
                "p_raw_home": 0.5, "p_raw_draw": 0.25, "p_raw_away": 0.25,
            }
        )
    return pd.DataFrame(rows)


# --- observations ------------------------------------------------------------


def test_one_quote_becomes_three_observations():
    out = to_observations(quotes(4), method="proportional")
    assert len(out) == 12
    assert set(out["outcome"]) == {"home", "draw", "away"}


def test_exactly_one_outcome_occurred_per_quote():
    out = to_observations(quotes(9), method="proportional")
    assert out["occurred"].sum() == 9


def test_probabilities_are_normalised_not_raw():
    out = to_observations(quotes(3), method="proportional")
    home = out[out["outcome"] == "home"]["p"]
    assert np.allclose(home, 0.5)  # 0.5 / 1.0, this book is already fair


def test_missing_normalised_columns_is_an_error():
    with pytest.raises(KeyError):
        to_observations(quotes(1))


def test_missing_result_is_an_error():
    frame = quotes(1).drop(columns=["result"])
    with pytest.raises(KeyError):
        to_observations(frame, method="proportional")


def test_unreadable_result_drops_the_whole_quote():
    frame = quotes(3)
    frame.loc[0, "result"] = "?"
    out = to_observations(frame, method="proportional")
    assert len(out) == 6  # two quotes survive, three rows each


def test_carried_columns_survive():
    out = to_observations(quotes(3), method="proportional")
    assert {"bookmaker", "season", "kind"} <= set(out.columns)


# --- Wilson interval ---------------------------------------------------------


def test_wilson_stays_inside_the_unit_square():
    low, high = wilson_interval([0, 1, 500], [500, 500, 500])
    assert (low >= 0).all() and (high <= 1).all()


def test_wilson_narrows_with_sample_size():
    small = wilson_interval([50], [100])
    large = wilson_interval([5000], [10000])
    assert (large[1] - large[0]) < (small[1] - small[0])


def test_wilson_brackets_the_observed_frequency():
    low, high = wilson_interval([250], [1000])
    assert low[0] < 0.25 < high[0]


def test_wilson_on_an_empty_bucket_is_nan():
    low, high = wilson_interval([0], [0])
    assert np.isnan(low[0]) and np.isnan(high[0])


# --- buckets -----------------------------------------------------------------


def perfectly_calibrated(n=6000, seed=0):
    """Observations whose outcomes really do happen at the quoted rate."""
    rng = np.random.default_rng(seed)
    p = rng.uniform(0.05, 0.95, size=n)
    return pd.DataFrame({"p": p, "occurred": rng.uniform(size=n) < p})


def test_a_calibrated_sample_sits_on_the_diagonal():
    table = bucket_calibration(perfectly_calibrated(), bins=10)
    assert (table["gap"].abs() < 0.05).all()


def test_a_biased_sample_does_not():
    sample = perfectly_calibrated()
    sample["occurred"] = sample["occurred"] & (np.arange(len(sample)) % 2 == 0)
    table = bucket_calibration(sample, bins=10)
    assert (table["gap"] < 0).all()


def test_bucket_counts_add_up_to_the_sample():
    sample = perfectly_calibrated()
    table = bucket_calibration(sample, bins=EQUAL_WIDTH_BUCKETS)
    assert table["observations"].sum() == len(sample)


def test_integer_bins_give_equal_counts():
    table = bucket_calibration(perfectly_calibrated(n=6000), bins=10)
    assert table["observations"].nunique() == 1


def test_a_probability_of_zero_is_not_dropped():
    sample = pd.DataFrame({"p": [0.0, 0.0, 0.5], "occurred": [False, False, True]})
    table = bucket_calibration(sample, bins=EQUAL_WIDTH_BUCKETS)
    assert table["observations"].sum() == 3


def test_grouping_splits_the_table():
    sample = perfectly_calibrated()
    sample["bookmaker"] = np.where(np.arange(len(sample)) % 2, "A", "B")
    table = bucket_calibration(sample, bins=5, by=["bookmaker"])
    assert set(table["bookmaker"]) == {"A", "B"}
    assert len(table) == 10


def test_missing_columns_is_an_error():
    with pytest.raises(KeyError):
        bucket_calibration(pd.DataFrame({"p": [0.5]}))


# --- summary and plot --------------------------------------------------------


def test_summary_counts_the_observations():
    sample = perfectly_calibrated()
    summary = calibration_summary(bucket_calibration(sample, bins=10))
    assert summary["observations"] == len(sample)
    assert summary["buckets"] == 10


def test_summary_gap_is_small_when_calibrated():
    summary = calibration_summary(bucket_calibration(perfectly_calibrated(), bins=10))
    assert summary["mean_absolute_gap"] < 0.02


def test_plot_writes_a_file(tmp_path):
    table = bucket_calibration(perfectly_calibrated(), bins=10)
    path = tmp_path / "curve.png"
    plot_calibration({"proportional": table}, path=path)
    assert path.exists() and path.stat().st_size > 0


def test_plot_handles_an_asymmetric_interval(tmp_path):
    """Wilson is not centred on the frequency, so one arm can sit the wrong side."""
    sample = pd.DataFrame({"p": [0.01] * 200, "occurred": [False] * 200})
    table = bucket_calibration(sample, bins=EQUAL_WIDTH_BUCKETS)
    assert (table["ci_low"] > table["frequency"]).any()
    path = tmp_path / "asymmetric.png"
    plot_calibration(table, path=path)
    assert path.exists()
