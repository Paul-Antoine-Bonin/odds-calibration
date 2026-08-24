"""Tests for the two normalisation methods."""

import numpy as np
import pandas as pd
import pytest

from oddscal.normalise import (
    METHODS,
    NORMALISED_COLUMNS,
    compare_methods,
    difference_by_probability_bucket,
    normalisation_error,
    normalise,
    solve_power_exponent,
)


def quotes(odds=((7.5, 4.75, 1.44), (1.30, 5.75, 10.0))):
    rows = []
    for i, (h, d, a) in enumerate(odds):
        rows.append(
            {
                "match_id": i,
                "bookmaker": "Bet365",
                "kind": "bookmaker",
                "result": "H",
                "odds_home": h, "odds_draw": d, "odds_away": a,
                "p_raw_home": 1 / h, "p_raw_draw": 1 / d, "p_raw_away": 1 / a,
            }
        )
    return pd.DataFrame(rows)


# --- proportional ------------------------------------------------------------


def test_proportional_sums_to_one():
    out = normalise(quotes(), "proportional")
    assert out[NORMALISED_COLUMNS].sum(axis=1).round(12).eq(1.0).all()


def test_proportional_divides_by_the_booksum():
    out = normalise(quotes([(2.0, 4.0, 4.0)]), "proportional")
    booksum = 0.5 + 0.25 + 0.25  # exactly 1, a fair book
    assert out["p_home"].iloc[0] == pytest.approx(0.5 / booksum)


def test_proportional_preserves_the_ratio_between_outcomes():
    q = quotes()
    out = normalise(q, "proportional")
    raw_ratio = q["p_raw_home"] / q["p_raw_away"]
    new_ratio = out["p_home"] / out["p_away"]
    assert new_ratio.to_numpy() == pytest.approx(raw_ratio.to_numpy())


def test_raw_columns_survive():
    out = normalise(quotes(), "proportional")
    assert "p_raw_home" in out.columns


# --- the power exponent ------------------------------------------------------


def test_a_fair_book_gives_an_exponent_of_one():
    raw = np.array([[0.5, 0.25, 0.25]])
    assert solve_power_exponent(raw)[0] == pytest.approx(1.0, abs=1e-9)


def test_an_overrounding_book_gives_an_exponent_above_one():
    raw = np.array([[0.55, 0.30, 0.25]])  # sums to 1.10
    assert solve_power_exponent(raw)[0] > 1.0


def test_the_exponent_actually_solves_the_equation():
    raw = np.array([[0.55, 0.30, 0.25], [0.80, 0.15, 0.12]])
    k = solve_power_exponent(raw)
    assert np.sum(raw ** k[:, None], axis=1) == pytest.approx([1.0, 1.0], abs=1e-12)


def test_a_book_summing_below_one_gives_an_exponent_below_one():
    # The archive contains a few. They must solve, not pin to the bracket.
    raw = np.array([[0.30, 0.25, 0.20]])  # sums to 0.75
    k = solve_power_exponent(raw)[0]
    assert k < 1.0
    assert np.sum(raw[0] ** k) == pytest.approx(1.0, abs=1e-12)


def test_a_row_with_a_nan_returns_nan():
    raw = np.array([[0.55, np.nan, 0.25]])
    assert np.isnan(solve_power_exponent(raw)[0])


def test_a_probability_of_one_or_more_returns_nan():
    # p == 1 makes p**k constant, so no exponent can solve the row.
    assert np.isnan(solve_power_exponent(np.array([[1.0, 0.3, 0.2]]))[0])


def test_the_wrong_shape_is_refused():
    with pytest.raises(ValueError):
        solve_power_exponent(np.array([0.5, 0.25, 0.25]))


# --- power normalisation -----------------------------------------------------


def test_power_sums_to_one():
    out = normalise(quotes(), "power")
    assert out[NORMALISED_COLUMNS].sum(axis=1).to_numpy() == pytest.approx(1.0, abs=1e-12)


def test_power_exposes_the_exponent():
    assert "power_k" in normalise(quotes(), "power").columns


def test_power_takes_more_from_the_longshot():
    # The headline behavioural difference between the two methods.
    q = quotes([(1.20, 6.00, 15.0)])          # heavy favourite, long outsider
    proportional = normalise(q, "proportional").iloc[0]
    power = normalise(q, "power").iloc[0]

    assert power["p_away"] < proportional["p_away"]     # longshot shaded harder
    assert power["p_home"] > proportional["p_home"]     # favourite shaded less


def test_the_two_methods_agree_on_a_fair_book():
    q = quotes([(2.0, 4.0, 4.0)])
    proportional = normalise(q, "proportional")[NORMALISED_COLUMNS].to_numpy()
    power = normalise(q, "power")[NORMALISED_COLUMNS].to_numpy()
    assert power == pytest.approx(proportional, abs=1e-9)


def test_an_unknown_method_is_refused():
    with pytest.raises(ValueError) as exc:
        normalise(quotes(), "shin")
    assert "proportional" in str(exc.value)


def test_every_declared_method_runs():
    for method in METHODS:
        assert not normalise(quotes(), method).empty


def test_missing_raw_columns_are_a_clear_error():
    with pytest.raises(KeyError) as exc:
        normalise(pd.DataFrame({"odds_home": [2.0]}), "proportional")
    assert "add_raw_probabilities" in str(exc.value)


# --- the checks --------------------------------------------------------------


def test_normalisation_error_is_negligible_for_both_methods():
    for method in METHODS:
        error = normalisation_error(normalise(quotes(), method))
        assert error.abs().max() < 1e-12


def test_normalisation_error_needs_normalised_columns():
    with pytest.raises(KeyError):
        normalisation_error(quotes())


# --- comparison --------------------------------------------------------------


def test_compare_methods_carries_both_and_the_difference():
    out = compare_methods(quotes())
    for column in ("p_home_proportional", "p_home_power", "p_home_diff", "power_k"):
        assert column in out.columns


def test_compare_methods_difference_is_power_minus_proportional():
    out = compare_methods(quotes())
    expected = out["p_away_power"] - out["p_away_proportional"]
    assert out["p_away_diff"].to_numpy() == pytest.approx(expected.to_numpy())


def test_compare_methods_drops_the_raw_columns():
    assert not any(c.startswith("p_raw_") for c in compare_methods(quotes()).columns)


def test_bucket_table_covers_every_quote_and_outcome():
    q = quotes([(1.2, 6.0, 15.0), (2.0, 3.5, 4.0), (7.5, 4.75, 1.44)])
    table = difference_by_probability_bucket(q)
    assert table["quotes"].sum() == 3 * 3


def test_bucket_table_shows_the_longshot_end_shaded_hardest():
    q = quotes([(1.2, 6.0, 15.0), (1.3, 5.5, 12.0), (1.25, 6.5, 14.0)])
    table = difference_by_probability_bucket(q).dropna(subset=["mean_difference"])
    lowest = table.iloc[0]
    highest = table.iloc[-1]
    assert lowest["mean_difference"] < 0 < highest["mean_difference"]
