# Validation record - 14 October 2026

Work scope: Param_Shelar only. No real City model, demo training run or production backtest
was run. Everything below is unit and contract testing on synthetic inputs.

## Second pass (fixes and optimization)

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

- A full run on real S1 data (needs the views in `s1_views_proposal.sql` and Kabir's database).
- Coverage >= 70% measured with `pytest --cov`.
- Four-hour run time and memory on the Raspberry Pi 5 reference host.
- Live PostgreSQL/PostGIS integration.

The S2 fault set does not establish the team's 19/20 cross-subsystem BIT metric; coordinate,
memo, API and deployment faults belong to their owners.
