"""Download the football-data.co.uk CSVs, one file per league and season.

The site serves files at a stable path:

    https://www.football-data.co.uk/mmz4281/<season>/<league>.csv

where <season> is the four-digit code for the two calendar years the season
spans ("2324" for 2023/24) and <league> is the division code ("E0" for the
English Premier League).

Not every league exists in every season, so a 404 is a normal outcome and not
an error. The downloader skips files it already has, so rerunning it is cheap
and only fetches what is missing.

Command line:

    python -m oddscal.download --leagues E0 SP1 --from 2015 --to 2024
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

import requests

BASE_URL = "https://www.football-data.co.uk/mmz4281"

# Divisions that carry bookmaker odds. The site publishes more, but these are
# the ones with deep and continuous odds coverage.
DEFAULT_LEAGUES = (
    "E0",   # England, Premier League
    "E1",   # England, Championship
    "E2",   # England, League One
    "E3",   # England, League Two
    "SC0",  # Scotland, Premiership
    "D1",   # Germany, Bundesliga
    "D2",   # Germany, 2. Bundesliga
    "I1",   # Italy, Serie A
    "I2",   # Italy, Serie B
    "SP1",  # Spain, La Liga
    "SP2",  # Spain, Segunda
    "F1",   # France, Ligue 1
    "F2",   # France, Ligue 2
    "N1",   # Netherlands, Eredivisie
    "B1",   # Belgium, Pro League
    "P1",   # Portugal, Primeira Liga
    "T1",   # Turkey, Super Lig
    "G1",   # Greece, Super League
)

# Bookmaker odds columns appear from the 2000/01 season onwards. Earlier files
# exist but carry results only, which is useless for a calibration study.
FIRST_SEASON_YEAR = 2000

DEFAULT_OUT_DIR = Path("data/raw")


def season_code(start_year: int) -> str:
    """Return the site's four-digit code for the season starting in `start_year`.

    2023 -> "2324", 1999 -> "9900", 2000 -> "0001".
    """
    if start_year < 1900 or start_year > 2999:
        raise ValueError(f"implausible season start year: {start_year}")
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def season_codes(from_year: int, to_year: int) -> List[str]:
    """Season codes for every season starting between the two years, inclusive."""
    if to_year < from_year:
        raise ValueError(f"empty range: from {from_year} to {to_year}")
    return [season_code(y) for y in range(from_year, to_year + 1)]


def build_url(season: str, league: str) -> str:
    return f"{BASE_URL}/{season}/{league}.csv"


def target_path(out_dir: Path, season: str, league: str) -> Path:
    return out_dir / season / f"{league}.csv"


@dataclass
class DownloadResult:
    """Outcome for a single league and season."""

    season: str
    league: str
    status: str  # "downloaded", "cached", "missing" or "failed"
    path: Path
    bytes_written: int = 0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status in ("downloaded", "cached")


def download_one(
    session: requests.Session,
    season: str,
    league: str,
    out_dir: Path,
    force: bool = False,
    timeout: float = 30.0,
) -> DownloadResult:
    """Fetch one CSV. Returns a result rather than raising, so one bad file
    never stops a long run."""
    path = target_path(out_dir, season, league)

    if path.exists() and not force:
        return DownloadResult(season, league, "cached", path, path.stat().st_size)

    url = build_url(season, league)
    try:
        response = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return DownloadResult(season, league, "failed", path, detail=str(exc))

    if response.status_code == 404:
        # This league simply did not run, or was not covered, that season.
        return DownloadResult(season, league, "missing", path, detail="404")

    if response.status_code != 200:
        return DownloadResult(
            season, league, "failed", path, detail=f"HTTP {response.status_code}"
        )

    # A handful of files come back as an HTML error page with a 200 status.
    head = response.content[:200].lstrip().lower()
    if head.startswith(b"<"):
        return DownloadResult(season, league, "failed", path, detail="HTML, not CSV")

    if not response.content.strip():
        return DownloadResult(season, league, "failed", path, detail="empty body")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return DownloadResult(season, league, "downloaded", path, len(response.content))


def download_many(
    leagues: Sequence[str],
    seasons: Sequence[str],
    out_dir: Path = DEFAULT_OUT_DIR,
    force: bool = False,
    delay: float = 0.5,
    progress: bool = True,
) -> List[DownloadResult]:
    """Fetch every (season, league) pair, pausing between network calls.

    `delay` only applies to requests that actually go out, so a rerun that hits
    the cache runs at full speed.
    """
    results: List[DownloadResult] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "oddscal/0.1 (research script)"})
        for season in seasons:
            for league in leagues:
                result = download_one(session, season, league, out_dir, force=force)
                results.append(result)
                if progress:
                    print(f"  {season} {league:4s} {result.status}", file=sys.stderr)
                if result.status in ("downloaded", "missing", "failed"):
                    time.sleep(delay)
    return results


def summarise(results: Iterable[DownloadResult]) -> str:
    counts = {"downloaded": 0, "cached": 0, "missing": 0, "failed": 0}
    total_bytes = 0
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
        total_bytes += r.bytes_written
    return (
        f"{counts['downloaded']} downloaded, {counts['cached']} cached, "
        f"{counts['missing']} missing, {counts['failed']} failed, "
        f"{total_bytes / 1_048_576:.1f} MiB on disk"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--leagues", nargs="+", default=list(DEFAULT_LEAGUES),
        help="division codes, for example E0 SP1",
    )
    parser.add_argument(
        "--from", dest="from_year", type=int, default=FIRST_SEASON_YEAR,
        help="first season start year",
    )
    parser.add_argument(
        "--to", dest="to_year", type=int, default=2024,
        help="last season start year",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--force", action="store_true", help="refetch files already on disk"
    )
    parser.add_argument(
        "--delay", type=float, default=0.5, help="seconds between network calls"
    )
    args = parser.parse_args(argv)

    seasons = season_codes(args.from_year, args.to_year)
    results = download_many(
        args.leagues, seasons, out_dir=args.out, force=args.force, delay=args.delay
    )

    print(summarise(results))
    failed = [r for r in results if r.status == "failed"]
    for r in failed:
        print(f"failed: {r.season} {r.league}: {r.detail}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
