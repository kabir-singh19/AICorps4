# IF-09 integration plan
**Documentation only.** S1 owns the database schema; no SQL migrations or result tables are implemented here. Snapshot reviewed: repository commit 829356486b259042d13aaea4e481ac4477c958b1.

## Existing S1 inputs
The current implementation uses schema `tasc` and singular table names, unlike the conceptual plural names in ICD Table 12.

| Existing object | S2 use / constraint |
|---|---|
| tasc.site | site_id, site_type, geometry, length_m, legs, road_id, network_version, as_of_date. Select a frozen network_version. |
| tasc.road | Road attributes joined by road_id; geometry is EPSG:32614 and distance is meters. Check road and AADT provenance. |
| tasc.crash | crash_id/date/year, KABCO severity, is_fsi, crash_type. Retain all in-area test F&SI crashes for the capture denominator. |
| tasc.crash_match | Crash-to-site assignment for a network_version; status/reason log unmatched records. Each crash must count once. |
| tasc.site_crash_year | Matched per-site/year crash and F&SI counts. It omits zero-crash site-years; explicitly fill those combinations in the future training panel. |
| tasc.site_feature | Long-form values keyed by site_id, feature_set, feature_name, with as_of_date and source. Planned frozen feature set: backtest_2022. |
| tasc.feature_set | backtest_2022 has cutoff 2022-12-31; current has no cutoff and must not silently feed the historical backtest. |

Read data through the shared database, not Kabir's CSVs or source modules. S1 currently plans a read-only role; S2 additionally needs limited write permissions on agreed result tables. Database credentials belong in the runtime environment and must not be committed.

## Planned S2 outputs from ICD Table 12
These tables are **absent** from the current S1 schema and require agreement/migrations owned by S1.

| Conceptual table | Required fields |
|---|---|
| runs | run_id, created, code_version, data_versions, as_of_date, seed, hyperparameters, published |
| predictions | run_id, site_id, mu, k, eb_weight, n_eb, p_fsi, fsi_rate, rank, flagged |
| explanations | run_id, site_id, feature, shap_value, rank |
| backtest | run_id, method, capture, ci_low, ci_high, n_test_fsi, flagged_miles |

Use the shared run_id and stable site_id to let S3 read risk context and S4 serve site/map/backtest pages. `ingest_run.run_id` identifies an ingest attempt and is not the model run identifier. Keep the meaning/time scale of mu and n_eb explicit. Agree storage for method-specific B/C predictions, paired differences, calibration, sensitivity outputs, provenance hashes, and artifact locations; ICD Table 12 alone does not specify all of these.

## Decisions to resolve before code
1. **Intersections and length:** current intersection length_m is null; 250 ft is a crash-assignment zone, not an agreed per-mile exposure. Segment geometry also runs through intersection zones. Agree the intersection rate denominator and treatment in cumulative network length without double counting.
2. **Frozen network:** the current build deletes/replaces a version and allocates new serial site IDs. Agree immutable versioning or stable IDs before claiming reproducible rankings.
3. **Analysis area:** ingestion is Brazos County, whereas FSR 3.2.1.1 defines the network inside College Station. Agree the city boundary, frozen network membership, and all-in-area test-crash denominator.
4. **HIN:** no HIN table or overlap mapping exists. Agree the published geometry/version, overlap rule, length accounting, and reconstruction labeling if GIS is unavailable. Do not treat HIN membership as a training feature.
5. **Historical provenance:** date stamps alone do not prove old information was available. Confirm dated road inventory, AADT, OSM/context features, source versions, and earlier-year lag construction.
6. **Readiness:** S1's README says feature production, HIN loading, and PostGIS-dependent integration are unfinished/unverified. Confirm match-rate quality and CRIS severity mapping before S2 uses real inputs.
7. **API boundary:** S4 owns REST routes and CSV/GeoJSON delivery. S2 provides stored values, not a competing web API or publication command.

ICD operator commands planned for later integration are `atsc train --run-id <id>` and `atsc backtest --run-id <id>`. The shared CLI does not exist yet; the empty files in this folder do not supply these commands.
