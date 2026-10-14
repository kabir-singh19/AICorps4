# Verification

Run `python -m pytest --cov=. --cov-report=term-missing --cov-fail-under=70` after installing
requirements. The stdlib core suite also runs automatically before each model run:
`python -m unittest discover -s tests/core -v`. Output invariants run before saving results.

Tests cover historical provenance, scope, duplicate/invalid records, EB hand calculations,
NB dispersion/offset, crash-weighted severity, calibration, ranking, paired bootstrap,
checksums, atomic failure isolation, preprocessing, ML offset/SHAP and exact full replay.
Core contract tests inject 20 S2 faults and check 20 valid synthetic inputs.

Missing pandas/XGBoost/psycopg causes explicit skips in development. A production validation
record must resolve skips and record complete coverage and integration evidence. CI for every
repository change remains a shared/root integration task outside this subsystem's edit scope.
