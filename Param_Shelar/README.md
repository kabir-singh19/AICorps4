# S2 - Risk Model and Backtest

Owner: Param Shelar. Source of scope: supplied Team 4 ConOps/FSR/ICD/EVP, October 2026.

The former placeholders now implement NB-SPF, CPU Poisson boosting with an exposure offset,
Empirical Bayes, crash-weighted severity, length flagging, exact TreeSHAP, paired bootstrap,
sensitivity scoring, immutable artifacts and exact replay. No real City model was trained.
See [validation.md](docs/validation.md) for measured checks and their limits.

## Install and test

From the repository root:

```bash
cd Param_Shelar
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest --cov=. --cov-report=term-missing --cov-fail-under=70
python cli.py bit
```

Python 3.11+ is required. Preserve `python -m pip freeze` with a validated production environment.
Each run records exact model-library versions; replay requires those versions and the original
source fingerprint. Fitting uses at most two CPU threads. Reference-host memory and four-hour
performance remain unmeasured. A test skip means its dependency is missing; install the full
requirements and run the entire suite before using a production result.

## Train it yourself

Synthetic smoke run, independent of unfinished S1 interfaces:

```bash
python make_demo.py --output demo_snapshot.json
python cli.py train --run-id demo-001 --config config/default.json --snapshot demo_snapshot.json
python cli.py train --run-id demo-001 --replay
python cli.py backtest --run-id demo-001
```

The fixture is labeled synthetic; its rates and HIN are not City results. The existing EB notebook
is retained as an exploratory reference. Production imports `empirical_bayes.py`.

For real data, supply an approved frozen IF-09 snapshot matching [interfaces.md](docs/interfaces.md):

```bash
python cli.py train --run-id backtest-001 --config config/default.json --snapshot /path/to/frozen_snapshot.json
```

For a database run, copy `config/database.example.json` to `config/local.json`, replace its explicit
placeholders, set `DATABASE_URL` in the environment, and run after S1 provides the required views:

```bash
python cli.py train --run-id backtest-001 --config config/local.json
```

A new run ID is required for changed inputs. `--replay` refits stored inputs and checks exact
prediction/ranking and backtest equality; it never overwrites a stored run. Training fits on
2015-2022 by default, consistent with the FSR; 2023-2025 labels are used only for scoring.

## Results and handoff

Each successful `outputs/<run-id>/` contains a checksum manifest, frozen snapshot/config,
native XGBoost model, JSON NB/severity/encoder state, feature table, B/C predictions as CSV/JSON,
SHAP factors, A/B/C backtest, paired differences, 5%/11%/20% and equal-HIN-share sensitivity,
calibration JSON/SVG, generated model card and BIT records. Completion requires successful
model reload and identical predictions. Failure leaves completed runs untouched.

`mu` and `n_eb` are history-window total crashes. `annual_total` and `annual_fsi` are site counts
per year. `fsi_rate` is K/A crashes per mile per year. S3 should use annual counts for benefit
calculations. TreeSHAP explains the ML log-count component before EB/severity; it is not causal.

```bash
python export_payload.py --run-id backtest-001 --output /path/to/s2_result_payload.json
```

The payload is for an agreed S1 transactional importer. S3/S4 must read the shared database,
not S2 working files. S1 owns migrations, import and permissions. S4 owns REST, publication,
CSV/GeoJSON delivery and the shared `atsc` command. `cli.py` supplies the S2 command handlers.

## Upstream dependencies

Real runs require the full College Station public-road network, all-in-area held-out crashes,
approved intersection risk exposure and disjoint network-length allocation, stable site IDs,
historical feature provenance and published HIN membership. Missing HIN permits an explicitly
labeled B/C diagnostic. Partial HIN mapping, leakage, unknown provenance and corridor-only scope
block the run. No other subsystem files or database tables were modified.
