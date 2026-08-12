"""Tests for the decimal odds to raw implied probability conversion."""

import numpy as np
import pandas as pd
import pytest

from oddscal.probabilities import (
    add_raw_probabilities,
    build_raw_probabilities,
    implied_probability,
    to_long_odds,
)


def wide_frame():
    return pd.DataFrame(
        {
            "match_id": [0, 1],
            "season": ["2324", "2324"],
            "division": ["E0", "E0"],
            "date": pd.to_datetime(["2023-08-12", "2023-08-12"]),
            "home_team": ["Burnley", "Arsenal"],
            "away_team": ["Man City", "Nott'm Forest"],
            "result": ["A", "H"],
            "B365H": [7.5, 1.3],
            "B365D": [4.75, 5.75],
            "B365A": [1.44, 10.0],
            "WHH": [7.0, 1.29],
            "WHD": [4.6, 5.5],
            "WHA": [1.45, 11.0],
            "MaxH": [8.0, 1.35],
            "MaxD": [5.0, 6.0],
            "MaxA": [1.5, 12.0],
        }
    )


def test_implied_probability_is_the_reciprocal():
    assert implied_probability([4.0]).iloc[0] == pytest.approx(0.25)
    assert implied_probability([2.0]).iloc[0] == pytest.approx(0.5)


def test_implied_probability_rejects_impossible_odds():
    # Decimal odds of 1.0 pay nothing back, below 1.0 is nonsense.
    values = implied_probability([1.0, 0.0, -3.0, np.nan])
    assert values.isna().all()


def test_implied_probability_handles_text():
    values = implied_probability(["2.0", "not a number"])
    assert values.iloc[0] == pytest.approx(0.5)
    assert np.isnan(values.iloc[1])


def test_raw_probabilities_sum_above_one():
    # This is the whole point: the excess over 1 is the bookmaker's margin.
    total = sum(implied_probability([7.5, 4.75, 1.44]))
    assert total > 1.0


def test_to_long_odds_gives_one_row_per_match_and_source():
    long = to_long_odds(wide_frame())
    # 2 matches, 2 real quote sources, and Max is an aggregate so it is excluded.
    assert len(long) == 4
    assert set(long["source"]) == {"B365", "WH"}


def test_aggregates_are_excluded_by_default():
    long = to_long_odds(wide_frame())
    assert "Max" not in set(long["source"])
    assert set(long["kind"]) == {"bookmaker"}


def test_aggregates_can_be_requested_explicitly():
    long = to_long_odds(wide_frame(), kinds=["aggregate"])
    assert set(long["source"]) == {"Max"}


def test_prefix_filter():
    long = to_long_odds(wide_frame(), prefixes=["B365"])
    assert set(long["source"]) == {"B365"}


def test_incomplete_triples_are_dropped():
    frame = wide_frame()
    frame.loc[0, "B365D"] = np.nan
    long = to_long_odds(frame, prefixes=["B365"])

    # The Bet365 quote on match 0 loses its draw price, so the whole row goes.
    assert long["match_id"].tolist() == [1]


def test_identity_columns_survive_the_reshape():
    long = to_long_odds(wide_frame(), prefixes=["B365"])
    assert long.iloc[0]["home_team"] == "Burnley"
    assert long.iloc[0]["result"] == "A"


def test_add_raw_probabilities():
    long = add_raw_probabilities(to_long_odds(wide_frame(), prefixes=["B365"]))
    row = long[long["match_id"] == 0].iloc[0]

    assert row["p_raw_home"] == pytest.approx(1 / 7.5)
    assert row["p_raw_draw"] == pytest.approx(1 / 4.75)
    assert row["p_raw_away"] == pytest.approx(1 / 1.44)


def test_build_raw_probabilities_end_to_end():
    long = build_raw_probabilities(wide_frame())
    assert {"p_raw_home", "p_raw_draw", "p_raw_away"}.issubset(long.columns)
    assert (long[["p_raw_home", "p_raw_draw", "p_raw_away"]].sum(axis=1) > 1).all()


def test_empty_input_returns_an_empty_frame_with_columns():
    long = to_long_odds(pd.DataFrame(columns=["match_id", "season"]))
    assert long.empty
    assert "odds_home" in long.columns
