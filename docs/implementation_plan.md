# Planned implementation sequence
Status: not started; this setup creates files only.

1. **Agree the S1 contract.** Close interface decisions, verify source provenance and matching, and agree result-table migrations/permissions. Freeze network and feature versions.
2. **Build database access and leakage gates.** Construct complete site/year panels, including zero-crash rows. Separate historical fitting inputs from 2023-2025 scoring labels.
3. **Build baselines and EB.** Represent published HIN, fit NB-SPF, hand-check EB, and establish comparable F&SI targets.
4. **Build ML and severity.** Fit the Poisson gradient-boosted model and overdispersion, apply EB, calibrate severity, and produce rate/rank/flag fields.
5. **Reach M2.** Run A/B/C end to end on identical frozen inputs; record coverage and length-budget evidence plus an honest go/no-go finding.
6. **Complete M4 evidence.** Add SHAP, paired bootstrap and sensitivity reports, model card, artifacts/reload, exact ranking replay, and reference-host timing.
7. **Integrate.** Supply agreed IF-09 outputs to S3/S4 and contribute S2 fault cases to team BIT validation.

Python/dependency choices and pinned versions are intentionally deferred. Keep S2 CPU-only and within the shared worker limits. Add meaningful tests as implementation is introduced; the current empty tests are not validation evidence.
