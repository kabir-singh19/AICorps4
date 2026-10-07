# S2 requirements and planned evidence
Source: supplied FSR and Execution and Validation Plan, Section 4.6. All evidence below is **planned**, not passing.

| FSR section | S2 obligation | Planned file(s) | Evidence / milestone |
|---|---|---|---|
| 3.2.1.1 | Predict F&SI rate for every segment and intersection in the College Station public-road analysis network. | database.py, ranking.py | Zero missing predictions; M2. |
| 3.2.1.6 | Compare published HIN (A), NB-SPF + EB (B), and ML-EB (C) on identical inputs. | hin_baseline.py, nb_spf.py, ml_risk.py | Frozen common network and A/B/C comparison; M2. |
| 3.2.1.7 | Apply EB with w = 1 / (1 + k * sum(mu)). | empirical_bayes.py | Review, valid weights, hand-checked example; M2. |
| 3.2.1.8 | Estimate P(K or A given a crash) and rank by expected F&SI per mile per year. | severity.py, ranking.py | Severity calibration curve; M4. |
| 3.2.1.9 | Flag highest-risk sites covering 11% +/- 0.5 percentage points of network length. | ranking.py | Length-budget check; M2. |
| 3.2.1.10 | Report A/B/C capture rates and 95% bootstrap intervals using at least 1,000 resamples. | backtest.py | Frozen backtest report; M4. |
| 3.2.1.11 | Goal: C exceeds A; report difference and interval regardless of outcome. | backtest.py | Paired comparison; M4. This is a goal, not a pass/fail threshold. |
| 3.2.1.12 | Provide five largest SHAP contributions in plain language for each flagged site. | explanations.py | Flagged-site explanation coverage; M4. |
| 3.2.1.21 | Store run ID, input versions, code version, seed, and hyperparameters; reproduce ranking exactly. | train.py, artifacts.py | Frozen-run replay; M4. |
| 3.2.2.2 | Complete full training and backtest within four hours on the reference host. | train.py, backtest.py | Timed reference-host run; M4. |
| 3.2.3.2.3 | Export trained models, feature tables, and per-site predictions for each run. | artifacts.py | Export/reload evidence; M4. |

## Integration obligations
S1 owns temporal leakage control (3.2.1.5), but S2 must independently refuse invalid inputs before fitting or evaluating a run. Team-level structured logs and BIT evidence include S2 stages and faults. Future S2 code participates in the plan's automated unit/integration checks and >=70% S1-S3 code coverage target.

The reference host is a Raspberry Pi 5, ARM64 Linux, 4 CPU cores, 8 GB RAM, and 128 GB storage, without a GPU. S2 shares the worker allocation with S1/S3: 2 vCPU, 3.5 GB RAM, and 20 GB scratch. These are planned constraints, not measured performance.

M2 target: 23 October 2026. M4 target: 11 December 2026. Record actual evidence, software version, run ID, tester, and unresolved anomalies when verification occurs.
