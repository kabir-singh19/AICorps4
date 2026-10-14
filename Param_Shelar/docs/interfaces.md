# IF-09 implementation contract

`database.py` reads existing singular `tasc.site`, `tasc.site_feature`, `tasc.crash` and
`tasc.crash_match` tables in a repeatable-read, read-only transaction. No S1 SQL was changed.
These proposed integration views do not exist yet; S1 owns their approval and implementation:

| View | Required columns | Purpose |
|---|---|---|
| tasc.s2_site_scope | site_id, network_version, in_analysis_area (bool), risk_length_mi (double), network_length_mi (double), road_name | Frozen full city membership and approved lengths; one row/site/version |
| tasc.s2_crash_scope | crash_id, in_analysis_area (bool) | Every crash classified once, including unmatched/no-coordinate records |
| tasc.s2_source_registry | network_version, feature_set, source, version, as_of_date, available_as_of, role | Historical provenance; one row/source in the selected snapshot |
| tasc.s2_hin_site | site_id, network_version, hin_version, in_hin (bool) | Full published HIN mapping |

View names are configurable and quoted as identifiers. Missing HIN is explicit: omit hin_view
for a B/C-only diagnostic. Segment membership follows the ICD's >=50% overlap rule;
intersection HIN membership requires team agreement. Sources have role predictor, history,
evaluation or baseline. A modern source relabeled 2022 does not prove historical availability;
the registry needs archival evidence. Test sources may be dated after 2022 and never feed fitting.

`risk_length_mi` is positive for every segment/intersection and sets exposure and rate units.
`network_length_mi` is a nonnegative allocation of unique road length, used only for flagging.
The team must agree intersection exposure and disjoint length allocation; S2 never guesses
that a 250-ft influence zone contributes a particular additional network length.

## Frozen snapshot

`make_demo.py` produces a complete executable, synthetic example. Top-level fields:

| Field | Contract |
|---|---|
| metadata | network_version, feature_set=backtest_2022, analysis_scope=college_station_public_roads, as_of_date, length_policy, nonempty data_versions, sources, history_years_loaded, test_years_loaded |
| sites | site_id, site_type, risk_length_mi, network_length_mi, as_of_date; road_name optional; complete boolean in_hin or entirely unavailable |
| features | site_id, feature_name, value, as_of_date, source; one row/site/selected feature; null means explicitly missing |
| history | site_id, year, crashes, known_crashes, fsi_crashes; unique site/year in selected history window |
| test_crashes | unique crash_id, crash_date in 2023-2025, severity K/A/B/C/O/U, explicit in_analysis_area boolean, site_id or null |

Source registry entries require source, version, as_of_date, available_as_of and role.
Predictor/history sources must be knowable by 2022-12-31. HIN metadata requires hin_version,
hin_source and hin_as_of_date: the consultant's crash-history cutoff, no later than 2022-12-31.
HIN publication can be later; it is a baseline and is excluded from model features.

Missing site/year combinations in an explicitly loaded year are zero-filled; missing years
are rejected. Known severity excludes U; F&SI is K/A. All in-area test crashes stay in the
denominator when site_id is null. The adapter checks that crash scope classifies every test
record; S1 must establish area membership from public location fields where coordinates are absent.

Every selected feature needs a provenance record for every site, including explicit nulls.
S1 currently emits only available type-specific attributes; it needs a complete approved
snapshot before full-network training. Features are a static historical snapshot; target counts
and crash-history lags are not predictors. A recorded 2017-2022 history sensitivity is supported,
while the FSR's 2015-2022 history remains the default.

## Output contract

`result_payload` prepares run metadata, B/C predictions, C explanations, primary A/B/C backtest,
full sensitivity/paired intervals and calibration. It does not write nonexistent tables. S1
must agree result schemas and atomic import. Ingest run IDs remain distinct from model run IDs.

| Field | Units |
|---|---|
| mu, n_eb | Total crashes over n_history_years |
| k, eb_weight | Site-total NB2 dispersion and EB blend weight |
| p_fsi | P(K/A given known-severity crash) |
| annual_total, annual_fsi | Expected crashes/site/year |
| fsi_rate | Expected K/A crashes/mile/year |
| rank, flagged | Lexical site-ID tie break; top 11% +/-0.5% by allocated network length |
| method | B or C; C supplies the primary map |

SHAP records include source feature, value, rank, plain-language description, log-count
contribution and a noncausal label. S4 owns display, exports, publication and rollback.
