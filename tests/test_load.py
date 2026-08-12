"""Tests for reading the raw CSVs.

Each test writes a small file that reproduces one quirk actually observed in
the football-data.co.uk archive.
"""

from pathlib import Path

import pandas as pd

from oddscal.load import (
    available_sources,
    decode,
    load_matches,
    parse_dates,
    read_raw_csv,
)

HEADER = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A"
ROW_1 = "E0,12/08/2023,Burnley,Man City,0,3,A,7.5,4.75,1.44"
ROW_2 = "E0,12/08/2023,Arsenal,Nott'm Forest,2,1,H,1.3,5.75,10.0"


def write(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(encoding))
    return path


def test_decode_prefers_utf8():
    assert decode("Köln".encode("utf-8")) == "Köln"


def test_decode_falls_back_to_latin1():
    # 11 files in the archive are latin-1, mostly older German seasons.
    assert decode("Köln".encode("latin-1")) == "Köln"


def test_read_strips_the_utf8_bom(tmp_path: Path):
    path = write(tmp_path / "SP1.csv", f"{HEADER}\n{ROW_1}\n", encoding="utf-8-sig")
    frame = read_raw_csv(path)
    assert list(frame.columns)[0] == "Div"


def test_read_drops_blank_filler_rows(tmp_path: Path):
    path = write(tmp_path / "E0.csv", f"{HEADER}\n{ROW_1}\n,,,,,,,,,\n,,,,,,,,,\n")
    assert len(read_raw_csv(path)) == 1


def test_read_pads_short_rows(tmp_path: Path):
    path = write(tmp_path / "E0.csv", f"{HEADER}\nE0,12/08/2023,Burnley,Man City\n")
    frame = read_raw_csv(path)
    assert len(frame) == 1
    assert frame.iloc[0]["B365H"] == ""


def test_parse_dates_handles_two_and_four_digit_years():
    parsed = parse_dates(pd.Series(["12/08/2023", "17/08/02"]))
    assert parsed.iloc[0].year == 2023
    assert parsed.iloc[1].year == 2002
    assert parsed.iloc[0].month == 8


def test_parse_dates_is_day_first():
    # 03/08 must be 3 August, not 8 March.
    assert parse_dates(pd.Series(["03/08/2023"])).iloc[0].day == 3


def test_load_matches_reads_a_season_tree(tmp_path: Path):
    write(tmp_path / "2324" / "E0.csv", f"{HEADER}\n{ROW_1}\n{ROW_2}\n")
    matches = load_matches(tmp_path)

    assert len(matches) == 2
    assert matches["season"].unique().tolist() == ["2324"]
    assert matches["home_team"].tolist() == ["Burnley", "Arsenal"]
    assert matches["result"].tolist() == ["A", "H"]
    assert matches["B365H"].tolist() == [7.5, 1.3]


def test_load_matches_accepts_the_old_ht_at_column_names(tmp_path: Path):
    # The Greek files from 2000 to 2005 use HT and AT.
    header = HEADER.replace("HomeTeam,AwayTeam", "HT,AT")
    write(tmp_path / "0001" / "G1.csv", f"{header}\nG1,20/09/2000,AEK,PAOK,1,0,H,2.1,3.2,3.4\n")
    matches = load_matches(tmp_path)

    assert len(matches) == 1
    assert matches.iloc[0]["home_team"] == "AEK"
    assert matches.iloc[0]["away_team"] == "PAOK"


def test_load_matches_drops_rows_without_a_valid_result(tmp_path: Path):
    write(tmp_path / "2324" / "E0.csv", f"{HEADER}\n{ROW_1}\nE0,13/08/2023,X,Y,,,,,,\n")
    assert len(load_matches(tmp_path)) == 1


def test_load_matches_filters_by_league_and_season(tmp_path: Path):
    write(tmp_path / "2324" / "E0.csv", f"{HEADER}\n{ROW_1}\n")
    write(tmp_path / "2324" / "SP1.csv", f"{HEADER}\n{ROW_2}\n")
    write(tmp_path / "2223" / "E0.csv", f"{HEADER}\n{ROW_1}\n")

    assert len(load_matches(tmp_path, leagues=["E0"])) == 2
    assert len(load_matches(tmp_path, seasons=["2324"])) == 2
    assert len(load_matches(tmp_path, leagues=["E0"], seasons=["2324"])) == 1


def test_load_matches_on_an_empty_tree(tmp_path: Path):
    (tmp_path / "2324").mkdir(parents=True)
    matches = load_matches(tmp_path)
    assert matches.empty
    assert "season" in matches.columns


def test_available_sources_reports_only_complete_triples(tmp_path: Path):
    partial = "Div,Date,HomeTeam,AwayTeam,FTR,B365H,B365D,B365A,WHH,WHD"
    write(tmp_path / "2324" / "E0.csv", f"{partial}\nE0,12/08/2023,A,B,H,2.0,3.0,4.0,2.1,3.1\n")
    found = available_sources(load_matches(tmp_path))

    assert "B365" in found
    assert "WH" not in found
