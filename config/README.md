# Configuration plan
No executable configuration is supplied yet. Future settings must be recorded with each run.

| Setting | Planned value / decision |
|---|---|
| Database connection | Runtime environment; no credentials in Git. |
| Database schema / network version | Existing schema tasc; agreed frozen network version TBD. |
| Historical feature set | backtest_2022; provenance verification still required. |
| Information cutoff | 2022-12-31 |
| Baseline history/fitting years | 2017-2022 |
| Evaluation years | 2023-2025 |
| F&SI definition | KABCO K and A |
| Primary flag share / tolerance | 0.11 / +/- 0.005 of network length |
| Bootstrap resamples / interval | 1,000 / 95% percentile interval |
| Sensitivity shares | 0.05 and 0.20; also HIN's actual share |
| Seed / hyperparameters / dependency versions | Select and freeze during implementation. |
| Intersection exposure and tie/threshold policy | Agree before ranking. |
| Artifact/log destinations | Runtime-configured, associated with run_id. |
| Reference runtime budget | Full train/backtest <=4 h; shared worker 2 vCPU / 3.5 GB RAM. |
