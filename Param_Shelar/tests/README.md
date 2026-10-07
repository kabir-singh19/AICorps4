# Planned S2 tests
All test modules are currently empty. There is no test suite to run yet, and these files do not demonstrate passing requirements.

| Empty file | Planned checks |
|---|---|
| [test_database_contract.py](test_database_contract.py) | IF-09 fields, joins, version isolation, and zero-crash site coverage. |
| [test_leakage.py](test_leakage.py) | Reject post-cutoff or undated inputs; exclude HIN and test labels from training. |
| [test_models.py](test_models.py) | A/B/C use the same frozen network; severity calibration evidence. |
| [test_empirical_bayes.py](test_empirical_bayes.py) | Hand-checked EB toy example, valid weights, and overdispersion behavior. |
| [test_ranking.py](test_ranking.py) | Complete coverage, valid rates, deterministic ties, and 11% length tolerance. |
| [test_backtest.py](test_backtest.py) | Capture denominator, paired bootstrap, equal-length comparison, sensitivity cases. |
| [test_reproducibility.py](test_reproducibility.py) | The same frozen run inputs reproduce an identical ranking. |
| [test_artifacts.py](test_artifacts.py) | Model/feature/prediction export and reload round trip. |

Create minimal local fixtures when writing tests; never use withheld 2023-2025 data for model selection. Integration checks need a validated S1/PostGIS snapshot. Reference-host timing and calibration reports are milestone evidence rather than placeholder unit tests.
