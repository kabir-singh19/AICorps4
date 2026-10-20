# S2 - Risk Model and Backtest

Owner: Param Shelar. Source of scope: supplied Team 4 ConOps/FSR/ICD/EVP, October 2026.

The former placeholders now implement NB-SPF, CPU Poisson boosting with an exposure offset,
Empirical Bayes, crash-weighted severity, length flagging, exact TreeSHAP, paired bootstrap,
sensitivity scoring, immutable artifacts and exact replay. Methods B and C have been trained and
backtested on S1's corridor database (run `m2-corridor-001`, below); the full-city run and method A
are still pending. See [validation.md](docs/validation.md) for measured checks and their limits.

## M2 corridor diagnostic (run `m2-corridor-001`, 20 Oct 2026)

Input: `Kabir_Singh/dumps/tasc_v0_2019.sql.gz` (network v0_2019, 185 segments + 2 intersections,
18.07 flagging miles) read as `s2_reader`; config `config/corridor_diagnostic.example.json`.
Scope `corridor_diagnostic`: three corridors, not the FSR 3.2.1.1 network, not the City backtest.
Code: commit 1e495a1 (fingerprint `db5e49dd…`); replay and backtest reproduced exactly.

Held-out 2023-2025: 59 in-area F&SI crashes (54 on a site, 5 without coordinates).

| Flagged share | B capture [95% CI] | C capture [95% CI] | B - C [95% CI] |
|---|---|---|---|
| 5% | 23.7% [13.6, 33.9] | 22.0% [11.9, 33.9] | +1.7 pp [-3.4, +6.8] |
| 11% | 47.5% [33.9, 59.3] | 47.5% [33.9, 59.3] | 0 (same 22 sites) |
| 20% | 55.9% [42.4, 67.8] | 55.9% [42.4, 67.8] | 0 (same sites) |

B and C are not distinguishable on this network: EB weights are 0.01-0.06, so both rankings
follow observed 2016-2022 history (Spearman 0.999 between them). Method A is unavailable until S1
loads the MPO HIN layer ([proposal](docs/s1_hin_view_proposal.sql); config template
`config/corridor_diagnostic_hin.example.json`). Charts and a summary are in
[docs/m2/m2-corridor-001/](docs/m2/m2-corridor-001/), made by `reports/m2_report.py`.

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
placeholders, set `DATABASE_URL` in the environment, and run against S1's views
(`Kabir_Singh/sql/05_s2_interface.sql`). For the M2 diagnostic on the S1 corridor network, start
from `config/corridor_diagnostic.example.json` instead:

```bash
python cli.py train --run-id backtest-001 --config config/local.json
```

A new run ID is required for changed inputs. `--replay` refits stored inputs and checks exact
prediction/ranking and backtest equality; it never overwrites a stored run. Training fits on
2016-2022 by default (CRIS no longer serves 2015); 2023-2025 labels are used only for scoring.

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
labeled B/C diagnostic, and the S1 corridor network runs as `corridor_diagnostic`, labeled in the
model card and manifest as not meeting FSR 3.2.1.1. Partial HIN mapping, leakage, unknown
provenance and any other scope block the run. No other subsystem files or database tables were modified.
