"""Read the downloaded CSVs into one tidy frame of matches.

The files are not uniform across twenty-five seasons:

- 11 of 450 are latin-1 rather than utf-8, and several carry a utf-8 BOM
- the early Greek files name the teams `HT` and `AT` instead of
  `HomeTeam` and `AwayTeam`
- most files end with a block of blank filler rows
- the odds columns come and go as bookmakers appear and disappear

`load_matches` absorbs all of that and returns one row per match with a stable
set of identity columns, plus whichever odds columns the registry knows about.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import pandas as pd

from . import sources

ENCODINGS = ("utf-8-sig", "latin-1")

# Older files use short names for the same thing.
COLUMN_ALIASES = {"HT": "HomeTeam", "AT": "AwayTeam"}

IDENTITY_COLUMNS = ["season", "division", "date", "home_team", "away_team", "result"]

VALID_RESULTS = ("H", "D", "A")


def decode(raw: bytes) -> str:
    """Decode CSV bytes, falling back from utf-8 to latin-1.

    Returns the text, and raises only if neither encoding works.
    """
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(
        "utf-8", raw, 0, 1, f"not decodable as any of {ENCODINGS}"
    )


def read_raw_csv(path: Path) -> pd.DataFrame:
    """Read one file with the encoding fallback, keeping the columns as published."""
    text = decode(path.read_bytes())

    # Ragged trailing rows are common: the site pads files with stray commas.
    # The C parser refuses them, so read through the csv module instead.
    reader = csv.reader(StringIO(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return pd.DataFrame()

    header = [cell.strip() for cell in rows[0]]
    width = len(header)
    body = [row[:width] + [""] * (width - len(row)) for row in rows[1:]]

    frame = pd.DataFrame(body, columns=header)
    return frame.loc[:, ~frame.columns.duplicated()]


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse the site's dates, which are day first and use 2 or 4 digit years."""
    return pd.to_datetime(series, dayfirst=True, format="mixed", errors="coerce")


def _tidy_one(frame: pd.DataFrame, season: str) -> pd.DataFrame:
    frame = frame.rename(columns=COLUMN_ALIASES)

    required = ("Div", "Date", "HomeTeam", "AwayTeam", "FTR")
    if any(col not in frame.columns for col in required):
        return pd.DataFrame()

    tidy = pd.DataFrame(
        {
            "season": season,
            "division": frame["Div"].astype(str).str.strip(),
            "date": parse_dates(frame["Date"]),
            "home_team": frame["HomeTeam"].astype(str).str.strip(),
            "away_team": frame["AwayTeam"].astype(str).str.strip(),
            "result": frame["FTR"].astype(str).str.strip().str.upper(),
        }
    )

    # Odds arrive as text because the whole file was read as text.
    for column in sources.odds_columns():
        if column in frame.columns:
            tidy[column] = pd.to_numeric(frame[column], errors="coerce")

    # A row without a usable result is not a match, it is filler.
    tidy = tidy[tidy["result"].isin(VALID_RESULTS)]
    tidy = tidy[tidy["home_team"].ne("") & tidy["away_team"].ne("")]
    return tidy


def load_matches(
    data_dir: Path = Path("data/raw"),
    leagues: Optional[Sequence[str]] = None,
    seasons: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Load every downloaded CSV into a single frame, one row per match.

    `leagues` and `seasons` filter by the file naming, so a subset can be loaded
    without reading the rest.
    """
    data_dir = Path(data_dir)
    frames: List[pd.DataFrame] = []

    for season_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        season = season_dir.name
        if seasons is not None and season not in seasons:
            continue
        for path in sorted(season_dir.glob("*.csv")):
            league = path.stem
            if leagues is not None and league not in leagues:
                continue
            tidy = _tidy_one(read_raw_csv(path), season)
            if not tidy.empty:
                frames.append(tidy)

    if not frames:
        return pd.DataFrame(columns=IDENTITY_COLUMNS)

    matches = pd.concat(frames, ignore_index=True, sort=False)

    # A stable identifier, so the long odds frame can be joined back.
    matches.insert(0, "match_id", range(len(matches)))
    ordered = IDENTITY_COLUMNS + [
        c for c in matches.columns if c not in IDENTITY_COLUMNS and c != "match_id"
    ]
    return matches[["match_id"] + ordered]


def available_sources(matches: pd.DataFrame) -> List[str]:
    """Prefixes whose three columns are all present in the loaded frame."""
    return [
        s.prefix
        for s in sources.all_sources()
        if all(col in matches.columns for col in s.columns)
    ]
