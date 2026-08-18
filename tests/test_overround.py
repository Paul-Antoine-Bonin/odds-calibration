"""Tests for the booksum, the overround and the margin."""

import numpy as np
import pandas as pd
import pytest

from oddscal.overround import (
    add_overround,
    booksum,
    drop_implausible_books,
    implausible_books,
    summarise_overround,
)


def quotes_frame():
    """Two quotes on the same match, one fair book and one that overrounds."""
    return pd.DataFrame(
        {
            "match_id": [0, 0],
            "division": ["E0", "E0"],
            "bookmaker": ["Pinnacle", "Bet365"],
            "kind": ["bookmaker", "bookmaker"],
            # Pinnacle: 1/2.0 + 1/4.0 + 1/4.0 = 1.00 exactly, a fair book that
            # nobody would really offer. Bet365: the same match priced wider.
            "odds_home": [2.0, 1.9],
            "odds_draw": [4.0, 3.8],
            "odds_away": [4.0, 3.8],
            "p_raw_home": [1 / 2.0, 1 / 1.9],
            "p_raw_draw": [1 / 4.0, 1 / 3.8],
            "p_raw_away": [1 / 4.0, 1 / 3.8],
        }
    )


def test_booksum_is_the_sum_of_the_three_probabilities():
    values = booksum(quotes_frame())
    assert values.iloc[0] == pytest.approx(1.0)
    assert values.iloc[1] == pytest.approx(1 / 1.9 + 2 / 3.8)


def test_booksum_requires_the_raw_probabilities():
    with pytest.raises(KeyError, match="p_raw_home"):
        booksum(pd.DataFrame({"odds_home": [2.0]}))


def test_overround_and_margin_are_not_the_same_number():
    # A book at 1.10 overrounds by 10% but keeps 9.09% of turnover.
    frame = pd.DataFrame(
        {"p_raw_home": [0.55], "p_raw_draw": [0.30], "p_raw_away": [0.25]}
    )
    row = add_overround(frame).iloc[0]

    assert row["booksum"] == pytest.approx(1.10)
    assert row["overround"] == pytest.approx(0.10)
    assert row["margin"] == pytest.approx(0.10 / 1.10)
    assert row["margin"] < row["overround"]


def test_margin_is_the_expected_loss_on_every_outcome():
    """Normalise proportionally and each bet loses exactly the margin per unit."""
    quotes = add_overround(quotes_frame())
    row = quotes.iloc[1]

    for outcome in ("home", "draw", "away"):
        normalised = row[f"p_raw_{outcome}"] / row["booksum"]
        expected_value = normalised * row[f"odds_{outcome}"] - 1.0
        assert expected_value == pytest.approx(-row["margin"])


def test_a_fair_book_has_no_margin():
    frame = pd.DataFrame(
        {"p_raw_home": [0.5], "p_raw_draw": [0.25], "p_raw_away": [0.25]}
    )
    row = add_overround(frame).iloc[0]

    assert row["overround"] == pytest.approx(0.0)
    assert row["margin"] == pytest.approx(0.0)


def test_add_overround_keeps_implausible_books():
    """They have to be countable before they are dropped."""
    frame = pd.DataFrame(
        {"p_raw_home": [0.30], "p_raw_draw": [0.20], "p_raw_away": [0.12]}
    )
    assert add_overround(frame).iloc[0]["booksum"] == pytest.approx(0.62)


def test_implausible_books_are_separated_from_the_rest():
    frame = pd.DataFrame(
        {
            "p_raw_home": [0.55, 0.30],
            "p_raw_draw": [0.30, 0.20],
            "p_raw_away": [0.25, 0.12],
        }
    )
    assert len(implausible_books(frame)) == 1
    assert len(drop_implausible_books(frame)) == 1
    assert implausible_books(frame).iloc[0]["booksum"] < 1.0


def test_a_book_summing_to_exactly_one_is_dropped_as_implausible():
    # The fair book is the boundary case: nobody prices one, so it is a defect.
    kept = drop_implausible_books(quotes_frame())
    assert kept["bookmaker"].tolist() == ["Bet365"]


def test_summary_over_the_whole_frame_is_one_row():
    summary = summarise_overround(quotes_frame())
    assert len(summary) == 1
    # Pinnacle's fair book is dropped, so only the Bet365 quote is counted.
    assert summary.iloc[0]["quotes"] == 1


def test_summary_by_bookmaker():
    frame = pd.concat([quotes_frame(), quotes_frame()], ignore_index=True)
    frame.loc[frame["bookmaker"] == "Pinnacle", "p_raw_home"] = 0.52

    summary = summarise_overround(frame, by=["bookmaker"])
    assert summary.loc["Pinnacle", "quotes"] == 2
    assert summary.loc["Bet365", "quotes"] == 2
    # Pinnacle now overrounds by 2%, Bet365 by more, so Pinnacle sorts first.
    assert summary.index.tolist() == ["Pinnacle", "Bet365"]


def test_summary_keeps_implausible_books_when_asked():
    summary = summarise_overround(quotes_frame(), drop_implausible=False)
    assert summary.iloc[0]["quotes"] == 2


def test_summary_reports_the_spread_within_a_group():
    frame = pd.DataFrame(
        {
            "bookmaker": ["Bet365"] * 3,
            "p_raw_home": [0.55, 0.60, 0.70],
            "p_raw_draw": [0.30, 0.30, 0.30],
            "p_raw_away": [0.25, 0.25, 0.25],
        }
    )
    summary = summarise_overround(frame, by=["bookmaker"]).iloc[0]

    assert summary["margin_p10"] < summary["margin_median"] < summary["margin_p90"]


def test_summary_of_an_empty_frame_has_no_rows():
    frame = pd.DataFrame(
        {"bookmaker": [], "p_raw_home": [], "p_raw_draw": [], "p_raw_away": []},
        dtype="float64",
    )
    assert summarise_overround(frame, by=["bookmaker"]).empty


def test_a_missing_leg_does_not_fake_a_tight_book():
    """Summed with the default skipna, a NaN leg would count as a zero."""
    frame = pd.DataFrame(
        {"p_raw_home": [0.55], "p_raw_draw": [np.nan], "p_raw_away": [0.25]}
    )
    assert np.isnan(add_overround(frame).iloc[0]["booksum"])
