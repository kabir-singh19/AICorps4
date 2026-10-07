# S2 - Risk Model and Backtest
Owner: Param Shelar | AI Corps Team 4 | AI Traffic-Safety Consultant

**Status: early implementation.** `empirical_bayes.py` is implemented and unit-tested on synthetic data (`pip install -r requirements.txt`, then `pytest tests/test_empirical_bayes.py`). The other modules and tests are still empty. No models have been fitted to real data, and no verification results are included.

## Scope and sources
S2 compares (A) the published consultant High-Injury Network, (B) a negative binomial SPF with Empirical Bayes, and (C) a Poisson gradient-boosted model with overdispersion, EB, and a severity model. It supplies per-site expected fatal/serious-injury (F&SI) rates, rankings, flags, SHAP factors, backtest results, and reproducible artifacts.

The source baseline is the supplied **Team4_AI_Traffic_Safety_Consultant_ConOps_FSR_ICD_EVP 2-1.pdf**, ConOps Revision C dated 1 October 2026 and its accompanying FSR, ICD, and Execution and Validation Plan. Read alongside [AITRAFFIC.md](../Initial_Research/AITRAFFIC.md), [DATASOURCES.md](../Initial_Research/DATASOURCES.md), and the existing [S1 README](../Kabir_Singh/README.md) and [schema](../Kabir_Singh/sql/init/01_schema.sql). The PDF supplies the current named ownership and requirements; older repository brainstorming does not expand this subsystem's scope.

## Planned files
| File | Intended responsibility |
|---|---|
| [database.py](database.py) | Read validated S1 inputs and persist S2 results through IF-09. |
| [leakage.py](leakage.py) | Validate input provenance, dates, and separation of training and evaluation data. |
| [hin_baseline.py](hin_baseline.py) | Represent the published consultant HIN as method A. |
| [nb_spf.py](nb_spf.py) | Fit the negative binomial safety performance function for method B. |
| [ml_risk.py](ml_risk.py) | Fit the Poisson gradient-boosted crash-count model for method C. |
| [empirical_bayes.py](empirical_bayes.py) | Estimate overdispersion and apply the EB blend for methods B and C. |
| [severity.py](severity.py) | Estimate and calibrate fatal/serious-injury probability using pre-cutoff crashes. |
| [ranking.py](ranking.py) | Calculate F&SI rates, rank all sites, and flag by cumulative network length. |
| [explanations.py](explanations.py) | Produce the five largest SHAP contributions for each flagged site. |
| [train.py](train.py) | Coordinate a frozen, reproducible training run. |
| [backtest.py](backtest.py) | Score A/B/C with paired bootstrap intervals and sensitivity comparisons. |
| [artifacts.py](artifacts.py) | Export and reload model files, feature tables, predictions, and run metadata. |
| [requirements.txt](requirements.txt) | Dependency list, to be selected and pinned during implementation. |

## Planning documents
- [Requirements and verification](docs/requirements.md)
- [Database interfaces and current gaps](docs/interfaces.md)
- [Frozen backtest protocol](docs/backtest_protocol.md)
- [Implementation sequence](docs/implementation_plan.md)
- [Model card template](docs/model_card.md)
- [Configuration plan](config/README.md)
- [Generated output policy](outputs/README.md)
- [Planned tests](tests/README.md)

## Boundaries
Kabir owns source ingestion, network construction, crash matching, feature production, and database schema. S2 exchanges data through IF-09; it does not read another owner's working files. Jose owns countermeasure tools and memos; Juan owns REST endpoints, website, deployment, and user-facing exports. Local artifact exports here support S2 reproducibility and independent model review.

Before implementation, agree with S1 on stable network/site IDs, intersection exposure and length, HIN mapping, historical provenance, and result-table migrations. Details are in the interface document. No shared files or database migrations are changed by this setup.
