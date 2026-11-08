# Interfaces

How the subsystems hand data to each other in this repo, mapped to the ICD (rev. 2-1). Where the
ICD does not define a field, it is defined here.

## Data flow

```
S1 PostGIS (IF-09, schema tasc)  ->  S2 citywide run  ->  integration/artifacts/<run_id>/
        |                                                    |            |
        +--> S3 tools (crash breakdown)  <-------------------+            |
                         S3 memos -> artifacts/<run_id>/memos/            |
                                                   S4 FastAPI reads the artifact folder (read-only)
```

S2, S3 and S4 never read raw CRIS, OSM or TxDOT files. S4 reads only the exported artifact
folder, so the deployed app needs no database.

## IF-09 views (S1 -> S2, S3), read with role `s2_reader`

| View | Key fields | Defined in |
|---|---|---|
| `tasc.s2_site_scope` | site_id, network_version, in_analysis_area, risk_length_mi, network_length_mi, road_name | `S1/sql/05_s2_interface.sql` |
| `tasc.s2_crash_scope` | crash_id, in_analysis_area | same |
| `tasc.s2_source_registry` | source, version, role, as_of_date, available_as_of | same |
| `tasc.s2_hin_site` | site_id, network_version, hin_version, in_hin, overlap_share | `S1/sql/08_hin.sql` |
| `tasc.s2_site_context` | site_id, route_name, jurisdiction, aadt_major, aadt_minor, x_m, y_m, lon, lat, geojson (EPSG:4326) | `S1/sql/09_s2_context.sql` |
| `tasc.s2_crash_detail` | crash_id, crash_date, crash_year, severity, site_id, match_status, crash_type, light/surface condition, flags angle, rear_end, single_vehicle, opposite_direction, sideswipe, night, wet | same |
| `tasc.site_feature` (feature_set `backtest_2022`) | site_id, feature_name, value_num/value_text, as_of_date, source | `S1/sql/04_features.sql`, `06_osm_features.sql` |

`jurisdiction` (not in the ICD): `TxDOT` for state route codes SH, US, IH, FM, BS, SL, SS, PR;
`TAMU` for campus streets; `City` otherwise; intersections joining both are `City/TxDOT`.
City-actionable means `City` or `City/TxDOT`.

## S2 run artifact (`integration/artifacts/<run_id>/`)

| File | Contents |
|---|---|
| `ranking.csv` | One row per site (7,224), sorted by rank. ICD Table 9 columns first, then the extras below |
| `sites.geojson` | RFC 7946 FeatureCollection, one Feature per site (LineString or Point, EPSG:4326), properties as listed below |
| `backtest.json` | Frozen 2022 backtest: targets KA and KABC, scenarios 5%, 11%, 20%, HIN share, HIN matched counts, S1 zero-length policy; methods A, B, C, Stack, LightGBM, LGB-Tot, Naive with capture, ci_low, ci_high, n_test_fsi, flagged_miles, flagged_share; paired differences |
| `explanations.json` | ICD Table 12 `explanations`: site_id, rank (1-5), feature, value, shap_value, direction, text (plain language), for every flagged site |
| `calibration.json` | Decile calibration of predicted vs observed 2023-2025 KA and KABC; severity calibration (Brier) |
| `bit.json`, `bit_campaign.json` | BIT checks on this run; 20 seeded faults and 20 clean refits |
| `model_card.md`, `capture_vs_share.png`, `calibration_ka.png` | Human-readable summary and charts |
| `config.json` | The exact config used |
| `manifest.json` | run_id, commit, as-of dates, data versions, input/config/ranking hashes, reload and refit checks, stage timings, SHA-256 of every file |
| `models/` | LightGBM text boosters and JSON model state. Local only (git-ignored), listed in the manifest |
| `memos/` | S3 output, see below |

### `ranking.csv` and GeoJSON properties

ICD Table 9 fields, with ICD names:

| Field | Definition |
|---|---|
| `site_id` | S1 site identifier (string) |
| `site_type` | `segment` or `intersection` |
| `road_name` | Primary road name (intersections: `A & B`) |
| `length_mi` | Segment length; intersections 0.0473 mi (250 ft influence zone) |
| `fsi_rate` | Method C (ML-EB) expected K+A crashes per mile per year in the forecast year |
| `rank` | 1 = highest `fsi_rate`; ties go to the lower site_id |
| `flagged` | In the top 11% (±0.5%) of network length, intersections counted at 0.0473 mi |
| `in_hin` | Member of the MPO HIN (segment: ≥ 50% of length within 30 m; intersection: within 30 m) |
| `memo_status` | `none` in the S2 export; S4 overlays `draft`, `blocked` or `pending` from `memos/` |

Fields not in Table 9, defined here:

| Field | Definition |
|---|---|
| `annual_fsi` | Expected K+A crashes per year (`fsi_rate × length_mi`) |
| `annual_kabc` | Expected K+A+B+C crashes per year (ML-EB) |
| `mu`, `k`, `eb_weight`, `n_eb`, `p_fsi` | ICD Table 12 prediction fields for method C: model crashes/yr, NB overdispersion, EB weight on the model, EB crashes/yr (all severities), P(K or A given a crash) |
| `network_length_mi` | Length under the 18 Oct S1 policy (intersections 0); used only in the sensitivity scenario |
| `fsi_rate_spf_eb`, `rank_spf_eb`, `flagged_spf_eb` | Method B for the same sites |
| `annual_fsi_stack` | Nov 4 Stack model, for comparison |
| `ka_3y`, `kabc_3y`, `tot_3y` and `<type>_3y` | Matched crashes 2023-2025 (the forecast's last three years) |
| `aadt`, `aadt_imputed` | TxDOT 2019 AADT; intersections major + minor approach; imputed = class median |
| `jurisdiction`, `route_name`, `city_actionable`, `rank_city_actionable` | See IF-09 above; rank among City-actionable sites |
| `signalized`, `legs`, `speed_limit`, `num_lanes`, `func_class`, `median_type` | Site attributes as of the feature dates |
| `lon`, `lat` | Segment midpoint or intersection center |
| `why` | The five SHAP factors as one plain-language string (flagged sites only) |

## S3 memos (`artifacts/<run_id>/memos/`)

| File | Contents |
|---|---|
| `<site_id>.json` | ICD 6.4.3 memo object: memo_id, site_id, run_id, status, created, model, sections, tool_results, grounding_check, tokens_in, tokens_out, cost_usd, plus seconds, revisions, price_assumption |
| `<site_id>.md` | Rendered memo (only when every check passed) |
| `<site_id>.evidence.json` | All tool calls with arguments and outputs, the placeholder values and the citations |
| `<site_id>.response.txt` | Raw LLM response |
| `summary.json` | Counts, median time and cost, totals, price assumption |

Memo `status` values: `draft` (passed every check, needs human review; the ICD's `published`
requires a reviewer), `blocked` (a grounding or completeness check failed), `pending` (the LLM
API was unreachable; rerun `make memos`).

Agent tools (ICD Table 11 names in brackets): `get_site_profile` [get_site_context],
`get_crash_breakdown` [get_crash_profile], `match_countermeasures` [search_countermeasures],
`compute_benefit` [compute_benefit_cost]. Placeholders: `{{name}}` for any key of
`evidence.numbers`, `{{cmf:<cmf_id>}}` for a matched CMF record.

## S4 REST API (IF-08)

Served by `S4_Web_App/backend` from a read-only copy of one artifact folder. See
`S4_Web_App/DEPLOY.md` for the endpoints implemented and their status.
