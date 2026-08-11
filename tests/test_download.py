"""Tests for the downloader.

Everything here runs offline. The network path is exercised with a fake session
so the suite stays fast and does not depend on football-data.co.uk being up.
"""

from pathlib import Path

import pytest

from oddscal.download import (
    DownloadResult,
    build_url,
    download_one,
    season_code,
    season_codes,
    summarise,
    target_path,
)


class FakeResponse:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


class FakeSession:
    """Returns queued responses and records the URLs it was asked for."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.requested = []

    def get(self, url, timeout=None):
        self.requested.append(url)
        return self._responses.pop(0)


CSV_BODY = b"Div,Date,HomeTeam,AwayTeam,FTR,B365H\nE0,12/08/23,Burnley,Man City,A,7.5\n"


def test_season_code_within_a_century():
    assert season_code(2023) == "2324"


def test_season_code_across_the_century_boundary():
    assert season_code(1999) == "9900"
    assert season_code(2000) == "0001"


def test_season_code_rejects_implausible_years():
    with pytest.raises(ValueError):
        season_code(1066)


def test_season_codes_is_inclusive_at_both_ends():
    assert season_codes(2021, 2023) == ["2122", "2223", "2324"]


def test_season_codes_rejects_a_reversed_range():
    with pytest.raises(ValueError):
        season_codes(2023, 2021)


def test_build_url():
    assert build_url("2324", "E0") == (
        "https://www.football-data.co.uk/mmz4281/2324/E0.csv"
    )


def test_download_writes_the_file(tmp_path: Path):
    session = FakeSession(FakeResponse(200, CSV_BODY))
    result = download_one(session, "2324", "E0", tmp_path)

    assert result.status == "downloaded"
    assert result.ok
    assert result.bytes_written == len(CSV_BODY)
    assert target_path(tmp_path, "2324", "E0").read_bytes() == CSV_BODY


def test_second_call_uses_the_cache_and_does_not_hit_the_network(tmp_path: Path):
    session = FakeSession(FakeResponse(200, CSV_BODY))
    download_one(session, "2324", "E0", tmp_path)

    # No queued response left: a second request would raise IndexError.
    result = download_one(session, "2324", "E0", tmp_path)

    assert result.status == "cached"
    assert len(session.requested) == 1


def test_force_refetches_even_when_cached(tmp_path: Path):
    session = FakeSession(FakeResponse(200, CSV_BODY), FakeResponse(200, CSV_BODY))
    download_one(session, "2324", "E0", tmp_path)
    result = download_one(session, "2324", "E0", tmp_path, force=True)

    assert result.status == "downloaded"
    assert len(session.requested) == 2


def test_404_is_reported_as_missing_not_failed(tmp_path: Path):
    session = FakeSession(FakeResponse(404, b"Not Found"))
    result = download_one(session, "0001", "T1", tmp_path)

    assert result.status == "missing"
    assert not result.ok
    assert not target_path(tmp_path, "0001", "T1").exists()


def test_html_error_page_with_a_200_is_rejected(tmp_path: Path):
    session = FakeSession(FakeResponse(200, b"<!DOCTYPE html><html>oops</html>"))
    result = download_one(session, "2324", "E0", tmp_path)

    assert result.status == "failed"
    assert result.detail == "HTML, not CSV"
    assert not target_path(tmp_path, "2324", "E0").exists()


def test_empty_body_is_rejected(tmp_path: Path):
    session = FakeSession(FakeResponse(200, b"   \n"))
    result = download_one(session, "2324", "E0", tmp_path)

    assert result.status == "failed"
    assert not target_path(tmp_path, "2324", "E0").exists()


def test_network_error_is_caught(tmp_path: Path):
    import requests

    class ExplodingSession:
        def get(self, url, timeout=None):
            raise requests.ConnectionError("no route to host")

    result = download_one(ExplodingSession(), "2324", "E0", tmp_path)

    assert result.status == "failed"
    assert "no route" in result.detail


def test_summarise_counts_every_status():
    results = [
        DownloadResult("2324", "E0", "downloaded", Path("x"), 1_048_576),
        DownloadResult("2324", "E1", "cached", Path("x"), 0),
        DownloadResult("0001", "T1", "missing", Path("x"), 0),
        DownloadResult("2324", "F1", "failed", Path("x"), 0),
    ]
    text = summarise(results)

    assert "1 downloaded" in text
    assert "1 cached" in text
    assert "1 missing" in text
    assert "1 failed" in text
    assert "1.0 MiB" in text
