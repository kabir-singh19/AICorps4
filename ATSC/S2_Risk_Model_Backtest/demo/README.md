# ATSC road evaluator (S2 demo)

A command-prompt style terminal tool that runs the ATSC crash-risk model (Subsystem 2) on any road in
College Station. It needs no database and no internet after the first setup. On every start it reloads
the saved LightGBM models, recomputes all 6,656 sites, and checks the ranking hash against the frozen run
`s2-citywide-v1.1-2026-11-08` (`875ded04c67a...`).

## Run it

You need Python 3.11 or newer (https://www.python.org/downloads/) and this repository
(`git clone https://github.com/kabir-singh19/AICorps4.git`, or Code > Download ZIP on GitHub and unzip).
The first run creates `demo/.venv` and installs the packages in `requirements.txt` (about 150 MB, needs
internet once). Later runs start in a few seconds.

**macOS / Linux** (Terminal):

    bash AICorps4/ATSC/S2_Risk_Model_Backtest/demo/atsc.sh

On a Mac, if it says LightGBM could not load, run `brew install libomp` and start it again.

**Windows**: double-click `ATSC\S2_Risk_Model_Backtest\demo\atsc.bat`, or in Command Prompt:

    AICorps4\ATSC\S2_Risk_Model_Backtest\demo\atsc.bat

When installing Python on Windows, tick "Add python.exe to PATH". Windows Terminal shows the colors best.

## What it does

Start-up (about 14 s): ATSC banner, then six sections where every line does real work:

- **SYSTEM**: host, and the python, numpy, pandas, scipy and lightgbm versions against the frozen run.
- **MODELS**: reloads the 18 LightGBM boosters and recomputes all 6,656 sites.
- **INTEGRITY**: SHA-256 of every bundle and cache file (progress bar), then the ranking hash.
- **LEAKAGE GATE**: the frozen snapshot passes the 2022-12-31 cutoff check, and 5 seeded post-cutoff
  records are each refused.
- **BACKTEST**: loads the frozen-2022 models and the 2023-2025 held-out crashes.
- **BUILT-IN TESTS**: BIT coverage and units, the 11% length budget, top-5 SHAP coverage, the EB hand
  formula on every site, and TreeSHAP additivity.

It ends with an ALL SYSTEMS GO panel (or RUNNING WITH WARNINGS in red if a check fails). Set
`ATSC_FAST=1` to skip the animation delays.

Home prompt `C:\ATSC>`:

| Type | Does |
|---|---|
| a road name or site ID (`holleman`, `texas ave`, `17683`) | lists matching sites, highest risk first |
| `top` | the 15 highest-risk sites |
| `map` | ASCII map of every site: flagged, HIN, top 9 ranks |
| `stats` | network overview: sites and miles by type, risk histogram, flagged by owner and road |
| `memos` | the 25 sites with an S3 safety memo |
| `hin` | ATSC vs HIN vs HSM scoreboard (1,000 paired bootstrap resamples, recomputed live) |
| `calib` | calibration: predicted vs observed 2023-2025 crashes by decile, checked against calibration.json |
| `test` | full self-test: hashes, leakage gate, BIT on the clean run, 8 injected faults, EB, SHAP, a second full reload |
| `lucky` | opens a random flagged site |
| `exit` | quit |

Results list: rank, road, type, ATSC flag, HIN membership, K+A per mile per year. Type a number to open a
site, `b` to go back, or a new search.

Site screen: rank out of 6,656, flagged or not, in the HIN or not; the model pipeline (LightGBM mu, EB
weight, EB estimate, P(injury | crash), P(K or A | injury), K+A per year, K+A per mile per year); the top
factors as red (raises risk) and green (lowers risk) bars from TreeSHAP; and the backtest line: the
frozen-2022 model's rank and its predicted vs observed K+A for 2023-2025. Keys:

| Key | Does |
|---|---|
| `1` | change a feature (traffic, speed, lanes, signals, crossings, sidewalks...) and re-run the real models |
| `2` | traffic +50% |
| `3` | remove or add the signal (intersections) or speed -10 mph (segments) |
| `4` | crash history 2016-2025 as colored bars |
| `5` | the full math for the site, step by step |
| `6` | compare with another road side by side |
| `7` | ATSC vs HIN scoreboard |
| `8` | sweep a feature across its range and watch the rate and rank change |
| `9` | the S3 safety memo (only on sites that have one) |
| `m` | the city map with this site marked |
| `r` | reset your changes |
| `b` | back to the list; or type any road name to search again |
| `q` | quit |

After a change, the tables show real vs what-if values and the change, and the rank shows where it was.

## Notes

- The live ranking is the 2026 forecast, refit with crashes through 2025. The backtest line and the
  scoreboard use the models frozen at 2022, which never saw 2023-2025.
- Intersections have 15 model inputs, segments 28.
- `cache/` holds the per-site inputs and the frozen-2022 models, built once from the S1 database by
  `prepare.py` (needs the database and the `s2_reader` password; not needed to run the tool).
- Tests: `demo/.venv/bin/python -m pytest ATSC/S2_Risk_Model_Backtest/demo/tests -q` (needs `pip install pytest`).
- Tested on Linux from a fresh copy with a new environment. Not yet run on macOS or Windows.
