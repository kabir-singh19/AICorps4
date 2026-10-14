# S2 requirements and evidence status

| FSR | Implementation | Current evidence |
|---|---|---|
| 3.2.1.1 | Complete-site predictions and BIT coverage | Contract/unit checks; actual City coverage pending S1 |
| 3.2.1.6 | HIN membership, NB-SPF+EB, Poisson ML+EB | Implemented; full A/B/C run awaits dependencies/data |
| 3.2.1.7 | empirical_bayes.py; site-total k (B from NB fit, C from 5-fold out-of-fold predictions) | Hand calculations, synthetic dispersion recovery tested |
| 3.2.1.8 | Weighted binomial severity, annual/rate conversion, calibration | Weighting/reload/Brier checks; City calibration pending |
| 3.2.1.9 | Ranked prefix closest to 11% with tolerance | Existing and expanded length/rank tests passing |
| 3.2.1.10-11 | Paired >=1,000 resamples, A/B/C and differences | Bootstrap/denominator/reproducibility checks passing |
| 3.2.1.12 | Exact TreeSHAP grouped to five original features | Code and additivity check; runtime test pending XGBoost |
| 3.2.1.21 | Immutable bundles, hashes, exact refit/reload | Atomic/checksum checks; full refit awaits dependencies |
| 3.2.2.2 | CPU <=2 threads, measured duration, four-hour gate | Reference-host full-run timing pending |
| 3.2.3.2.3 | Native ML and JSON model state, features/predictions | Artifact safety tested; trained ML export/reload pending |

S2 independently enforces the cutoff and emits JSON stage logs. Its 20 seeded contract faults
and 20 good inputs test S2 only; they do not prove the team's cross-subsystem BIT or false-alarm
criteria. See validation.md for exact test outcomes and skips. No other subsystem was modified.
