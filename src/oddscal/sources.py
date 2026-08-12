"""Registry of the odds columns published by football-data.co.uk.

Each odds quote occupies three columns sharing a prefix, one per 1X2 outcome:
`B365H`, `B365D`, `B365A` for Bet365. A trailing `C` on the prefix marks the
closing quote rather than the opening one, so `B365C*` is Bet365 at kickoff.

Three kinds of source live in these files and they are not interchangeable:

- `bookmaker`  an actual price a punter could take, margin included
- `exchange`   Betfair, a market price net of commission rather than a quote
- `aggregate`  the maximum or the mean across bookmakers, computed by the site

Aggregates matter here. The maximum across bookmakers is not a price anyone
offered on all three outcomes at once, and its implied probabilities can sum to
less than one. Including it in a calibration study silently invents a bookmaker
that never existed, so it is tagged and excluded by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

BOOKMAKER = "bookmaker"
EXCHANGE = "exchange"
AGGREGATE = "aggregate"

OPENING = "opening"
CLOSING = "closing"


@dataclass(frozen=True)
class OddsSource:
    """One triple of 1X2 odds columns."""

    prefix: str
    name: str
    kind: str
    phase: str

    @property
    def columns(self) -> Tuple[str, str, str]:
        """The (home, draw, away) column names in the raw CSV."""
        return (f"{self.prefix}H", f"{self.prefix}D", f"{self.prefix}A")


_SOURCES: Tuple[OddsSource, ...] = (
    # Bookmakers, opening quote.
    OddsSource("B365", "Bet365", BOOKMAKER, OPENING),
    OddsSource("BW", "Bet&Win", BOOKMAKER, OPENING),
    OddsSource("IW", "Interwetten", BOOKMAKER, OPENING),
    OddsSource("PS", "Pinnacle", BOOKMAKER, OPENING),
    OddsSource("WH", "William Hill", BOOKMAKER, OPENING),
    OddsSource("VC", "VC Bet", BOOKMAKER, OPENING),
    OddsSource("LB", "Ladbrokes", BOOKMAKER, OPENING),
    OddsSource("GB", "Gamebookers", BOOKMAKER, OPENING),
    OddsSource("SB", "Sportingbet", BOOKMAKER, OPENING),
    OddsSource("SJ", "Stan James", BOOKMAKER, OPENING),
    OddsSource("BS", "Blue Square", BOOKMAKER, OPENING),
    OddsSource("SO", "Sporting Odds", BOOKMAKER, OPENING),
    OddsSource("SY", "Stanleybet", BOOKMAKER, OPENING),
    OddsSource("1XB", "1XBet", BOOKMAKER, OPENING),
    # Bookmakers, closing quote.
    OddsSource("B365C", "Bet365", BOOKMAKER, CLOSING),
    OddsSource("BWC", "Bet&Win", BOOKMAKER, CLOSING),
    OddsSource("IWC", "Interwetten", BOOKMAKER, CLOSING),
    OddsSource("PSC", "Pinnacle", BOOKMAKER, CLOSING),
    OddsSource("WHC", "William Hill", BOOKMAKER, CLOSING),
    OddsSource("VCC", "VC Bet", BOOKMAKER, CLOSING),
    OddsSource("1XBC", "1XBet", BOOKMAKER, CLOSING),
    # Betting exchange.
    OddsSource("BF", "Betfair", EXCHANGE, OPENING),
    OddsSource("BFE", "Betfair Exchange", EXCHANGE, OPENING),
    OddsSource("BFC", "Betfair", EXCHANGE, CLOSING),
    OddsSource("BFEC", "Betfair Exchange", EXCHANGE, CLOSING),
    # Site-computed aggregates, not quotes.
    OddsSource("BbMx", "Betbrain maximum", AGGREGATE, OPENING),
    OddsSource("BbAv", "Betbrain mean", AGGREGATE, OPENING),
    OddsSource("Max", "Market maximum", AGGREGATE, OPENING),
    OddsSource("Avg", "Market mean", AGGREGATE, OPENING),
    OddsSource("MaxC", "Market maximum", AGGREGATE, CLOSING),
    OddsSource("AvgC", "Market mean", AGGREGATE, CLOSING),
)

BY_PREFIX: Dict[str, OddsSource] = {s.prefix: s for s in _SOURCES}


def all_sources() -> List[OddsSource]:
    return list(_SOURCES)


def quote_sources() -> List[OddsSource]:
    """Sources that are a real price: bookmakers and the exchange, no aggregates."""
    return [s for s in _SOURCES if s.kind != AGGREGATE]


def bookmaker_sources() -> List[OddsSource]:
    return [s for s in _SOURCES if s.kind == BOOKMAKER]


def odds_columns() -> List[str]:
    """Every 1X2 odds column name known to the registry."""
    return [col for s in _SOURCES for col in s.columns]
