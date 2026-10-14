# Validation record - 14 October 2026

Base repository: kabir-singh19/AICorps4, c86b28b8436d6c2e25db1ababf36888b70ea20db.
Work scope: Param_Shelar only. Tester: automated checks in this task.
No real City model or production backtest was trained.

Executed: Python syntax compilation, stdlib BIT suite, and pytest.
Pytest: **71 passed, 5 skipped, 20 seeded-fault subtests passed**.
The BIT contains 22 test methods, including a 20-case S2 contract fault set and 20
known-good synthetic input cases. All seeded faults were rejected and all good cases accepted.
Evidence: verification/pytest.txt and verification/bit.json.

Passing numerical checks include EB hand calculations, synthetic dispersion recovery,
NB-SPF exposure scaling and JSON reload, crash-weighted binomial severity and reload,
calibration/Brier calculations, ranking and length budgets, paired bootstrap and unmatched
crash denominators, immutable/checksummed artifacts and failure isolation.

Unavailable dependencies caused explicit skips:
- pandas: preprocessing, multi-threshold evaluation and complete-run replay test modules.
- XGBoost: Poisson model exposure and exact TreeSHAP runtime test.
- psycopg: SQL identifier contract test. No live PostgreSQL/PostGIS integration was attempted.

Dependency installation could not access PyPI in this environment. NumPy/SciPy/pytest were
available from existing cached wheels. Full pipeline training, trained ML file reload,
coverage >=70%, reference-host timing/memory and database integration remain unverified.
Install requirements and run the full documented suite before accepting a production result.

The S2 fault set does not establish the team's 19/20 cross-subsystem BIT metric; coordinate,
memo, API and deployment faults belong to their owners. A root CI workflow was not edited
because the user limited this task to subsystem 2. Shared result schemas/import and production
inputs remain explicit S1/S4 integration dependencies, documented in interfaces.md.
