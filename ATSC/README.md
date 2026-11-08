# ATSC: AI Traffic-Safety Consultant

ECEN 403 Team 4. Ranks College Station road sites by expected fatal and serious-injury crashes,
backtests the ranking against the MPO High-Injury Network, drafts countermeasure memos, and
serves the results in a web app. Controlling documents: `docs/Team4_ATSC_ConOps_FSR_ICD_EVP_rev2-1.pdf`.

| Folder | Subsystem | Owner |
|---|---|---|
| `S1_Road_Network_Database/` | Road network, features, PostGIS database | Kabir Singh |
| `S2_Risk_Model_Backtest/` | Risk model and backtest (Python package `S2_Risk_Model_Backtest`) | Param Shelar |
| `S3_Countermeasure_Agent/` | Countermeasure agent and memos | Jose Ruiz Garcia |
| `S4_Web_App/` | FastAPI + React web app, deployment | Juan Lopez |
| `integration/` | Run artifacts, logs, demo assets, figures | Lead |
| `docs/` | Controlling documents and change requests | Lead |

Run everything from this folder. S2 runs as a package: `python -m S2_Risk_Model_Backtest.<module>`.

## Build and run

To serve only the website from the committed run (Docker only, no pipeline), use the
copy-paste blocks (Ubuntu, macOS, Windows) in the [top-level README](../README.md#run-the-website-on-a-new-machine).

```bash
make demo     # data -> model -> memos -> web; stages are cached (integration/.stamps/)
make serve    # web app on http://127.0.0.1:8000
make test     # S1-S4 suites, frontend build, Playwright
make clean    # drop the database volume, the run folder, the web bundle and build
```

Needs Docker (PostGIS), Python 3.12 (`.venv`), Node 22 and, for `make memos`, a TAMU AI Chat
key in `~/.config/atsc/memo.env` (outside the repo; without it memos are marked `pending`).
Logs and per-stage timings go to `integration/logs/` (`make_<stage>.log`, `make_timings.jsonl`).
How the subsystems hand data to each other: `INTERFACES.md`. Deployment: `S4_Web_App/DEPLOY.md`.

Operator commands (ICD Table 13) are in `./atsc` (run `./atsc -h`): `ingest`, `network build`,
`match`, `features --as-of`, `train`, `backtest`, `memos`, `bit` (`--show` prints the BIT log),
`publish`, `rollback`, `runs`, `logs prune`. Each command appends JSON events to
`integration/logs/atsc.jsonl` and exits non-zero on failure. Logs are kept 90 days.
Change requests: `docs/change_requests/`. Forms for the ECEN 404 human checks: `docs/handoff/`.

Current run: `integration/artifacts/s2-citywide-2026-11-08/` (model card, backtest, charts,
memos). `make demo` from a clean database on 8 Nov 2026 reproduced its ranking hash exactly.
