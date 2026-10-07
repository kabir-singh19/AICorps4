# CLAUDE.md

Context for AI agents working in this repository. The source of truth is the team's baseline
PDF, **Team4_AI_Traffic_Safety_Consultant_ConOps_FSR_ICD_EVP 2-1.pdf**, which holds four documents:

- **ConOps** Revision C, 1 Oct 2026 (operating concept)
- **FSR**, the Functional System Requirements, Rev – Draft (binding "shall" requirements)
- **ICD**, the Interface Control Document, Rev – Draft (interfaces IF-01 to IF-12, tables, commands)
- **EVP**, the Execution and Validation Plan, Rev – Draft (milestones, backtest protocol, tests)

The PDF is not in the repo. Section numbers below (for example "FSR 3.2.1.7") point into it.
When the PDF and older files in this repo disagree, the PDF wins. Within the PDF, the FSR text
takes precedence over the ICD and EVP (FSR 2.3).

## Project in one paragraph

**ATSC (AI Traffic-Safety Consultant)** is a capstone project by AI Corps Team 4 for the City of
College Station, TX. It reproduces the analysis part of a consultant traffic-safety action plan.
The comparison point is the Kimley-Horn **High-Injury Network (HIN)** in the Bryan/College Station
MPO Comprehensive Safety Action Plan, built from 2017–2022 crashes, from a plan of about $200,000.
The ATSC does four things:

1. Ranks every road site by expected fatal and serious-injury (F&SI) crashes per mile per year,
   using an ML model with Empirical Bayes correction.
2. Backtests that ranking against the HIN on the 2023–2025 crashes.
3. Uses an LLM agent to draft cited countermeasure memos for the flagged sites.
4. Serves the results in a web app.

The goal is an **honest, measured answer**. If the model does not beat the HIN, that is a valid
result, and it gets reported, not hidden.

## Team and ownership

Each subsystem has one owner. Subsystems exchange data **only** through the shared database
(IF-09) and the REST API (IF-08). Never read another subsystem's working files or CSVs directly.

| Subsystem | Owner | Repo folder | Responsibility |
|---|---|---|---|
| S1 Road Network, Features, and Database | Kabir Singh | `Kabir_Singh/` | Ingest IF-01 to IF-05, build the network, map-match crashes, store features with as-of dates, enforce the leakage cutoff, own the PostgreSQL/PostGIS schema. Kabir is also custodian of the ICD. |
| S2 Risk Model and Backtest | Param Shelar (also team leader) | `Param_Shelar/` | Methods A, B, C; EB; severity model; SHAP; flagging; backtest with bootstrap; sensitivity; model card; artifacts |
| S3 Countermeasure Agent | Jose Ruiz Garcia | (none yet) | IF-06 countermeasure library, IF-10 tools, IF-07 LLM calls, prompts, grounding checks, cost logging |
| S4 Web Application and Deployment | Juan Lopez | (none yet) | FastAPI (IF-08), React/MapLibre frontend, exports (IF-11), containers, hosting. Juan is also the City liaison. |

Other people involved:
- **Client:** City of College Station; contact Sam Rivera (IT).
- **Sponsor:** Prof. Nowka.
- **Course and program:** John Lusher II, P.E.; T/As Roman Venegas and Sabyasachi Gupta.

Stay inside the owner's subsystem when asked to work on one. If a change needs another
subsystem (for example, new result tables in S1's schema), describe what is needed rather than
editing that owner's code.

## Repository layout

- `Kabir_Singh/` is the S1 baseline. It has `docker-compose.yml` (PostgreSQL 16 + PostGIS),
  `sql/init/01_schema.sql` (schema `tasc`, leakage trigger), `ingest.py`,
  `sql/02_build_network.sql`, `sql/03_map_match.sql`, and `tests/`. Its README lists what has
  and has not actually been run.
- `Param_Shelar/` is the S2 skeleton. The `.py` files, the tests, and `requirements.txt` are
  **empty placeholders**. Planning lives in `Param_Shelar/docs/`:
  - `requirements.md`
  - `interfaces.md` (S1 schema mapping and open interface decisions)
  - `backtest_protocol.md`
  - `implementation_plan.md`
  - `model_card.md`
- Root `.md` files hold early research and brainstorming:
  - `AITRAFFIC.md` (proposal)
  - `DATASOURCES.md`
  - `RESEARCH.md`
  - `IDEAS.md`
  - `FINANCE.md` and `BUDGETING.md` (consulting spend)
  - `README.md` (kickoff notes)

  Use them for background only, never for scope.

## Fixed definitions (do not change without an FSR change)

- **Analysis area:** public roads inside College Station city limits that appear in the TxDOT
  roadway inventory or OSM. Crash ingest covers all of Brazos County.
- **Site:** a road segment of 0.1 mi (±0.05 mi), or an intersection. An intersection is any node
  where **3 or more public road legs** meet, with a **250 ft influence zone**. Crashes inside the
  zone go to the intersection; crashes outside it go to the nearest segment.
- **F&SI** means KABCO **K (fatal) and A (suspected serious injury)**. Unknown severity maps to
  `U` and is excluded from F&SI.
- **CRS:** all lengths and distances are computed in **EPSG:32614** (UTM 14N, meters) and
  reported in miles and feet. Interchange data (GeoJSON, API) uses EPSG:4326.
- **Backtest split:** training and ranking may use only information knowable as of
  **31 Dec 2022**. Training history is 2015–2022 (the HIN used 2017–2022). The test window is
  **2023–2025**.
- **Flagging:** the highest-ranked sites whose total length is **11% ± 0.5%** of network length,
  the same share the HIN covers.
- **Capture rate:** 2023–2025 F&SI crashes on flagged sites, divided by **all** 2023–2025 F&SI
  crashes in the analysis area.

## S2 methods (FSR 3.2.1.6 to 3.2.1.12)

- **A, consultant HIN as published.** Match HIN geometry to sites when **50% or more** of a
  segment's length overlaps (ICD Table 5). Record the HIN's actual share of network length. HIN
  membership is never a training feature.
- **B, negative binomial SPF + EB** per the AASHTO Highway Safety Manual (industry standard).
- **C, ATSC ML-EB.** A gradient-boosted model with **Poisson loss** and segment length as the
  offset, plus estimated overdispersion `k` (Var = μ + kμ²), the EB blend, and a severity model
  for P(K or A). The ranking metric is expected F&SI per mile per year.
- **EB weight:** `w = 1 / (1 + k·Σμ)`, where Σμ is the predicted total over the history years.
  The EB estimate is `w·Σμ + (1 − w)·observed`. The weight must lie in (0, 1). Hand-check it on a
  toy example.
- **Explanations:** the top 5 SHAP features for every flagged site, in plain language (for
  example, "45 mph posted speed").
- **CPU only.** A full training and backtest run must finish in **≤ 4 h** on the reference host.

### Backtest protocol (EVP 4.2)

1. **Freeze inputs.** Record the version and as-of date of every source. Run the leakage check;
   any feature dated after 31 Dec 2022 **stops the run**.
2. **Rank** with methods A, B, and C on identical inputs. Flag 11% of length for B and C. Use
   the HIN as published for A.
3. **Score** each method's capture rate on the 2023–2025 F&SI crashes.
4. **Bootstrap.** Resample the test-window F&SI crashes 1,000 times with replacement. Report 95%
   CIs (2.5th and 97.5th percentiles) for each method and for the paired differences C−A and
   B−A.
5. **Fairness check.** If the HIN's share is not 11%, also compare B and C at the HIN's exact
   share.
6. **Sensitivity.** Repeat at 5% and 20% of network length, and with total crashes instead of
   F&SI.
7. **Report** every result, including ones that favor the HIN.

There are roughly 100 F&SI crashes per year in Brazos County, so about 300 in the test window.

## Interfaces (ICD)

| ID | Interface | Owner |
|---|---|---|
| IF-01 | TxDOT CRIS crash CSVs, Brazos County 2015–2025, one file per year | S1 |
| IF-02 | TxDOT roadway inventory (lanes, speed, functional class, median, AADT + AADT year). AADT must be dated 2022 or earlier for backtests. | S1 |
| IF-03 | OSM `.osm.pbf` (geometry, sidewalks, bus stops, schools, bars). The snapshot date is the as-of date. | S1 |
| IF-04 | City streetlight GIS. If unavailable, use OSM `lit` tags and log the gap. | S1 |
| IF-05 | MPO HIN layer. If not received by 9 Oct 2026, reconstruct it from published maps and note the limitation. | S1 / S2 |
| IF-06 | Countermeasure library CSV (FHWA PSC + CMF Clearinghouse) | S3 |
| IF-07 | TAMU AI Chat API (OpenAI-compatible, HTTPS; key from chat.tamu.ai, held in an env var) | S3 |
| IF-08 | REST API under `/api/v1`, OpenAPI 3.1 at `/api/v1/openapi.json` | S4 |
| IF-09 | Database: SQL over TCP 5432, internal Docker network only | S1 |
| IF-10 | Agent tools: `get_crash_profile`, `get_site_context`, `search_countermeasures`, `compute_benefit_cost` | S3 |
| IF-11 | Exports: sites as CSV (RFC 4180) and GeoJSON; memos as PDF only | S4 |
| IF-12 | Operator CLI with JSON logs; exits non-zero on failure | S1–S3 |

**Core tables (ICD Table 12):**

| Table | Fields |
|---|---|
| `sites` | `site_id`, `site_type`, `geom`, `length_mi`, `road_name`, `attributes` |
| `crashes` | `crash_id`, `crash_date`, `severity`, `crash_type`, `geom`, `site_id`, `match_dist_ft`, `match_status` |
| `features` | `site_id`, `as_of_date`, name/value pairs, source and source date |
| `runs` | `run_id`, `created`, `code_version`, `data_versions`, `as_of_date`, `seed`, `hyperparameters`, `published` |
| `predictions` | `run_id`, `site_id`, `mu`, `k`, `eb_weight`, `n_eb`, `p_fsi`, `fsi_rate`, `rank`, `flagged` |
| `explanations` | `run_id`, `site_id`, `feature`, `shap_value`, `rank` |
| `backtest` | `run_id`, `method`, `capture`, `ci_low`, `ci_high`, `n_test_fsi`, `flagged_miles` |
| `memos` | `memo_id`, `site_id`, `run_id`, `status`, `content` (JSON), `tool_results`, `tokens`, `cost_usd` |
| `bit_log` | `test_run_id`, `timestamp`, `test`, `result`, `details` |

S1's actual schema uses schema `tasc` and singular names (`tasc.site`, `tasc.crash`,
`tasc.crash_match`, `tasc.site_crash_year`, `tasc.site_feature`, `tasc.feature_set`). The S2
result tables do not exist yet. See `Param_Shelar/docs/interfaces.md` for the mapping.

**Site feature properties (ICD Table 9):**
- `site_id`
- `site_type`
- `road_name`
- `length_mi`
- `fsi_rate`
- `rank` (1 = highest risk)
- `flagged`
- `in_hin`
- `memo_status`

**Operator commands (ICD Table 13):**
- `atsc ingest --source <name> --path <file>`
- `atsc network build`
- `atsc match`
- `atsc features --as-of <date>`
- `atsc train --run-id <id>`
- `atsc backtest --run-id <id>`
- `atsc memos --run-id <id> [--flagged]`
- `atsc bit`
- `atsc publish` / `atsc rollback --run-id <id>`

The shared `atsc` CLI does not exist yet.

## Hard constraints

- **Hosting:** one Linux host with ≤ 4 CPU cores, 8 GB RAM, and 128 GB storage, and no GPU. The
  reference test host is a Raspberry Pi 5 (ARM64), so images are built for amd64 and arm64.
  Container caps are in ICD Table 2; the batch worker running S1/S2/S3 gets 2 vCPU and 3.5 GB.
  Keep memory use modest.
- **Stack:** Python ≥ 3.11, PostgreSQL ≥ 15 with PostGIS 3, Docker, FastAPI, React, MapLibre GL.
  Open source only.
- **Data:** public sources only. Store no personal identifiers beyond what CRIS already
  publishes. Send only public site attributes, crash aggregates, and countermeasure records to
  the LLM.
- **Secrets:** API keys and DB credentials go in environment variables or an ignored secrets
  file. Never put them in code, commits, or the browser.
- **Reproducibility:** every run stores its run_id, data versions, code version, seed, and
  hyperparameters. Re-running a run_id must reproduce the ranking **exactly**, so set and record
  all seeds.
- **Input validation (FSR 3.2.3.1.2):** check counts, required fields, coordinate bounds, dates,
  and severity codes, and stop the pipeline if **more than 2%** of records fail.
  > ⚠️ Known inconsistency: EVP Table 8 tests "3% bad records stops," and
  > `Kabir_Singh/ingest.py` uses `BAD_RECORD_LIMIT = 0.03` (≥ 3%). The FSR's 2% governs. Flag
  > this rather than silently changing S1 code.
- **Map-matching:** at least 95% of geocoded F&SI crashes matched, and every unmatched crash
  logged with its reason. Coordinates are noisy, so the tolerance is generous but logged.
- **LLM rule (S3):** the LLM never computes a number. Deterministic tools compute every value.
  The memo grounding check blocks any number not in the tool results, and any countermeasure
  without a CMF ID or FHWA source. Use temperature 0.2 for memos and 0 for extraction. Calls
  time out after 60 s, with 3 retries on 429/5xx. Target ≤ $1.00 and ≤ 2 min per memo, and
  alert at 75% of the API budget.
- **Degraded mode:** if the LLM is down, the map, site pages, and backtest stay up, and memos
  show "pending." A failed model run leaves the last published run in place.
- **Scope:** planning-level only, with no engineering design and no PE-sealed work. Memos state
  when an engineering study is needed. The chat page is a **stretch goal** only after M6. Memo
  export is PDF only.

## Verification

A requirement counts as verified only when its evidence (a log, report, or test record) is stored
in the repo.
- **Unit tests:** pytest on every change, with ≥ 70% coverage on S1–S3 code.
- **BIT:** detects ≥ 19 of 20 seeded faults (shifted dates, swapped lat/lon, post-cutoff
  feature, duplicate crashes, invented memo number, missing citation) and raises ≤ 1 false alarm
  in 20 good runs.
- **S2 pass criteria (EVP Table 8):**

  | Requirement | Pass criterion |
  |---|---|
  | Network coverage | 0 sites missing a prediction |
  | Methods | A, B, and C on identical inputs |
  | EB | Weights in (0, 1), plus a toy hand-check |
  | Severity | Calibration curve reported |
  | Flagging | Flagged length is 11% ± 0.5% |
  | Backtest | 1,000-resample CIs |
  | Explanations | Top-5 SHAP for every flagged site |
  | Reproducibility | Identical re-run |
  | Training time | ≤ 4 h |
  | Artifacts | Exported and reloaded |

Do not describe empty or placeholder tests as validation evidence.

## Milestones

| ID | Milestone | Target date |
|---|---|---|
| M0 | Documents submitted | 1 Oct 2026 |
| M1 | Data acquired and validated | 9 Oct 2026 |
| M2 | Go/no-go: A, B, C end to end | 23 Oct 2026 |
| M3 | City Hall presentation | Nov 2026 |
| M4 | Model v1 frozen; fall report | 11 Dec 2026 |
| M5 | Agent MVP | 19 Feb 2027 |
| M6 | Web beta | 12 Mar 2027 |
| M7 | Validation complete | 9 Apr 2027 |
| M8 | City Council presentation | Apr 2027 |
| M9 | Final delivery | 7 May 2027 |

**M2 outcomes:**
- **B or C beats A:** go.
- **Neither beats A but the pipeline is sound:** go, report the finding, shift effort to the
  agent, and use the HIN as the memo site list.
- **HIN or CRIS data is missing:** hold and escalate, compare B and C with each other, and
  reconstruct the HIN.

## Working conventions

- Write plainly, and state what has and has not actually been run. Never claim results, match
  rates, or capture rates that were not computed from real data.
- Keep subsystem boundaries. When an interface decision is open (see "Decisions to resolve" in
  `Param_Shelar/docs/interfaces.md`), surface it instead of picking an answer silently.
- Record requirement changes in the repo. Changing a "shall" requires approval from the team
  leader, the sponsor, and the City.
