# Implementation and remaining handoff

Implemented: frozen-contract validation and provenance gates; read-only IF-09 adapter;
complete zero-filled historical panels; NB2 SPF, Poisson boosting, site-total dispersion and EB;
crash-weighted severity with held-out-site calibration; risk ranking and approved length budgets;
exact source-feature TreeSHAP; paired 1,000-resample backtest, fairness and sensitivity;
JSON/native model artifacts, atomic run completion, reload checks and exact replay commands;
S2 BIT, structured logs, result-payload export, configuration and synthetic fixtures.

The owner runs training. Before real-data use:

1. S1 supplies full City scope, stable IDs, approved lengths, historical provenance and complete features.
   Until then, an M2 diagnostic can run on the S1 corridor network with
   `config/corridor_diagnostic.example.json` once S1 adopts the views in `s1_views_proposal.sql`.
2. S1/S2 agree HIN mapping, including intersections, and all-in-area test membership.
3. Install requirements and run the full suite with coverage; resolve every skip/failure.
4. Run the frozen model and record all results, including outcomes favoring HIN.
5. Measure full-run timing/resources on the reference host.
6. S1 implements agreed result storage/import; S4 delegates CLI handlers, publishes results and adds
   repository-wide CI. A root GitHub workflow was not added because this task is scoped to S2.

No real backtest, DB integration, reference-host result or team-level BIT claim is made.
