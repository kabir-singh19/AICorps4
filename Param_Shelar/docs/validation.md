# Validation record

Work scope: Param_Shelar only.

## Third pass: M2 corridor run on S1's database (20 October 2026)

Environment: Ubuntu 24.04, Python 3.12.3, xgboost 3.4.1, Docker 29.1.3 with
`postgis/postgis:16-3.4`. Database restored from `Kabir_Singh/dumps/tasc_v0_2019.sql.gz` and
`sql/05_s2_interface.sql` per S1's README Option 1; S2 connected as `s2_reader`.

S1 numbers checked before the run, all equal to S1's record: 185 segments + 2 intersections,
F&SI match 156/159 = 98.11%, 18.07 flagging miles, and `s2_reader` writes refused
(`permission denied for table crash`, `... site_feature`).

- `pytest --cov=. --cov-fail-under=70` with `DATABASE_URL` set: **87 passed, 0 skipped, 84%
  coverage** (verification/pytest_m2.txt). New: a live-database contract test, a partial HIN
  view that must block loading, and the HIN config template that must be blocked.
- `cli.py bit`: pass (verification/bit_m2.json).
- `cli.py train --run-id m2-corridor-001 --config config/local.json`: 187 sites, 935 feature
  records, 818 history rows, 4,869 test crashes; leakage check passed; 1.3 s.
- `--replay`: exact. `cli.py backtest`: stored backtest reproduced exactly.
- `export_payload.py`: written to `outputs/m2-corridor-001/s2_result_payload.json`.
- Code fingerprint `db5e49dd…` = commit 1e495a1. Later commits add tests, which are part of the
  fingerprint, so replay this run from 1e495a1.

Results: README "M2 corridor diagnostic" and [m2/m2-corridor-001/](m2/m2-corridor-001/)
(`summary.json` and four charts).

Findings from this run:

- B and C flag the same 22 sites at 11% and 20%. EB weights are 0.01-0.06 because sites average
  about 20 crashes over 2016-2022, so both rankings follow observed history. With 59 test F&SI
  crashes, no B vs C difference is detectable (5%: +1.7 pp, 95% CI -3.4 to +6.8).
- Totals predicted vs observed 2023-2025 (matched crashes): 1,576 vs 1,490, Spearman 0.88 across
  sites; the top quintile is over-predicted (991 vs 878). F&SI: 44 predicted vs 54 observed, under-predicted
  in 4 of 5 quintiles, each quintile within Poisson noise.
- Severity calibration is close to a single point: 1,072 of 1,073 held-out known-severity crashes
  fall in one bin (predicted 2.3%, observed 3.2%). The curve is reported but says little.
- Intersection 2 (Texas Ave & University Dr) ranks first in B and C with 0 test F&SI. Its rate
  uses 0.0473 mi exposure and it costs 0 flagging miles. Its features are all missing, so its top
  SHAP factor is the missing-AADT indicator (+2.16), which in effect encodes "intersection".
- `func_class` and `median_type` are still raw TxDOT codes; `feature_labels` has no translations.
- Labeling gap: the manifest and backtest.json carry `analysis_scope` but no explicit
  "not FSR 3.2.1.1" text; the model card and diagnostics state it.

Method A is unavailable: no HIN layer in S1. It needs S1 to adopt
[s1_hin_view_proposal.sql](s1_hin_view_proposal.sql), a team decision on the intersection HIN
rule, and real values in `config/corridor_diagnostic_hin.example.json`.

## Second pass, 14 October 2026 (fixes and optimization, synthetic inputs only)

Environment: Python 3.12, numpy 2, scipy, pandas, xgboost, psycopg installed in a test-only
virtual environment.

- `python -m pytest --deselect tests/test_reproducibility.py`: **82 passed, 20 seeded-fault
  subtests passed, 0 skipped.** The XGBoost, SHAP, preprocessing, multi-share backtest and
  database tests that were skipped in the first pass now run and pass.
- `python -m unittest discover -s tests/core` (the pre-run BIT suite): **24 tests OK.**
- `tests/test_reproducibility.py` was deliberately not run: it fits a full run on the
  synthetic demo snapshot. Run it before M2 evidence is recorded.
- Bootstrap timing, 3 methods x 1,000 resamples, synthetic crashes: 300 crashes 0.17 s -> 0.024 s,
  5,000 crashes 2.66 s -> 0.13 s. Point estimates are identical; intervals differ only by random draws.

Changes verified by those tests:

| Change | Test |
|---|---|
| `corridor_diagnostic` scope accepted and labeled; other scopes still rejected | core `test_corridor_diagnostic_is_accepted_and_labeled`, seeded fault 2 |
| History defaults to 2016-2022 | core `test_2015_history_is_not_required` |
| Method C k from 5-fold out-of-fold predictions, reproducible | `test_ml_out_of_fold_predictions_never_see_their_own_site` |
| Absent intersection features become explicit, registered nulls | `test_absent_intersection_features_become_explicit_nulls` |
| NumPy paired bootstrap | core bootstrap tests, `test_backtest.py` |

## First pass (original package)

Pytest: 71 passed, 5 skipped (pandas, XGBoost and psycopg were not installed); 20 seeded-fault
subtests passed. Evidence: verification/pytest.txt and verification/bit.json.

## Not yet verified

- Method A and a full-city (FSR 3.2.1.1) run.
- Four-hour run time and memory on the Raspberry Pi 5 reference host.

The S2 fault set does not establish the team's 19/20 cross-subsystem BIT metric; coordinate,
memo, API and deployment faults belong to their owners.
