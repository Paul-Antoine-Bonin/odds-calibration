# odds-calibration

Are bookmakers well calibrated?

Odds imply a probability. If a bookmaker quotes 20% on a thousand matches, about two
hundred should happen. This repo checks that against twenty-five seasons of football
results, and measures where the margin sits.

No calibration results yet. So far the data collection works.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Get the data

```bash
python -m oddscal.download                      # 18 leagues, seasons 2000/01 to 2024/25
python -m oddscal.download --leagues E0 --from 2020 --to 2024   # a smaller slice
```

Files land in `data/raw/<season>/<league>.csv`, which is git-ignored. Reruns are
cached, so only missing files are fetched. A league that did not run in a given season
returns 404, which counts as missing rather than as a failure.

## What the source gives

Measured on a full run of the default league set, seasons 2000/01 to 2024/25:

| | |
|---|---|
| Files downloaded | 450 of 450, no failures |
| Size on disk | 45.1 MiB |
| Matches with a result | 157,274 |
| Of which priced by Bet365 on 1X2 | 144,391 |

That clears the 50,000 match target in the roadmap with room to spare.

Two things the loader will have to handle: 11 of the 450 files are latin-1 rather than
utf-8, and the odds columns differ between seasons, since some bookmakers have
disappeared and newer files add aggregate columns.

## Run the tests

```bash
pytest
```

Roadmap and progress: [TODO.md](TODO.md)
