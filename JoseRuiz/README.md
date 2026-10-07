# S3 - Countermeasure Recommendations and Memos

Owner: Jose | AI Corps Team 4 | AI Traffic-Safety Consultant

**Status: planning.** This README proposes the S3 structure based on the supplied S1 and S2 descriptions. Implementation and test status have not been verified. The filenames below are planned; this document does not claim that code, recommendations, or validation results already exist.

## Scope and sources

S3 turns the road-site information supplied by S1 and the risk results supplied by S2 into evidence-backed countermeasure recommendations and draft consulting memos. It explains which treatments may suit a site, what evidence supports them, what information is missing, and what needs engineering review.

The project baseline identified by S2 is **Team4_AI_Traffic_Safety_Consultant_ConOps_FSR_ICD_EVP 2-1.pdf**, ConOps Revision C dated 1 October 2026, with its accompanying FSR, ICD, and Execution and Validation Plan. Confirm this proposed implementation plan against those documents before treating it as an approved requirement list.

Read alongside [AITRAFFIC.md](../Initial_Research/AITRAFFIC.md), [DATASOURCES.md](../Initial_Research/DATASOURCES.md), and the existing [S1 README](../Kabir_Singh/README.md) and [schema](../Kabir_Singh/sql/init/01_schema.sql). Review the S2 README for the definitions and limitations of its risk outputs.

## Planned workflow

1. Read a versioned site record and its associated S2 risk results through the agreed IF-09 database interface.
2. Identify candidate countermeasures using documented applicability rules and available site characteristics.
3. Retrieve supporting evidence from a curated, versioned countermeasure catalog.
4. Compare eligible candidates using a documented scoring method. Report missing inputs and uncertainty explicitly.
5. Generate a draft memo explaining the site, proposed treatments, evidence, assumptions, and review needs.
6. Persist structured recommendations and memo content for S4 to display and export.

## Planned files

| File | Intended responsibility |
|---|---|
| `database.py` | Read approved S1/S2 inputs and persist S3 results through IF-09. |
| `catalog.py` | Load and validate countermeasure evidence, applicability conditions, and source metadata. |
| `eligibility.py` | Check whether a treatment applies to the site's road type, features, and relevant crash pattern. |
| `recommendations.py` | Assemble candidate treatments and record selection or rejection reasons. |
| `scoring.py` | Compare eligible treatments using explicit criteria and versioned assumptions. |
| `benefits.py` | Estimate treatment effects only when a compatible baseline and applicable evidence are available. |
| `memos.py` | Produce draft memos from validated inputs and cited evidence. |
| `validation.py` | Check required fields, source references, numerical consistency, and unsupported claims. |
| `run.py` | Coordinate a reproducible recommendation and memo-generation run. |
| `artifacts.py` | Save local review artifacts, configuration, and run metadata. |
| `requirements.txt` | Declare and pin dependencies during implementation. |

Use Python for the proposed initial implementation. Select libraries after the database contract and first working example are defined.

## Inputs and outputs

| Direction | Planned content |
|---|---|
| S1 → S3 | Stable site IDs, network version, site type, road features, feature dates, and any approved crash-pattern summaries. |
| S2 → S3 | Model/run ID, per-site expected fatal/serious-injury (F&SI) results, units, rankings, flags, and available explanations. |
| Evidence catalog → S3 | Treatment descriptions, applicability conditions, source references, effect estimates where supported, and limitations. |
| S3 → IF-09 / S4 | Site-linked recommendations, evidence references, comparison results, assumptions, missing-data flags, draft memo content, and run metadata. |

These are proposed data needs, not confirmed database columns or tables. Request missing fields through the owning subsystem; do not assume they already exist.

## Evidence and recommendation rules

- Record the source and applicability conditions for each recommendation. Candidate evidence sources include the FHWA CMF Clearinghouse and FHWA countermeasure guidance; individual entries must be reviewed before use.
- Treat S2 SHAP factors as explanations of model predictions, not proof that changing a feature will reduce crashes.
- Use crash modification factors (CMFs) only when their outcome, severity, road context, and treatment definition match the analysis. Do not apply an all-crash CMF to F&SI outcomes without supporting justification.
- Align baseline units and time periods before estimating benefits. A per-mile rate must not be treated as an annual site crash count.
- Do not automatically multiply CMFs for combined treatments. Record an evidence-supported combination method or evaluate treatments separately.
- Label unavailable costs and effect estimates as unknown. Add cost-effectiveness calculations only after cost sources, analysis periods, and assumptions are agreed.
- Keep selection rules and calculations reproducible. If an LLM drafts memo text, constrain it to validated inputs and retrieved evidence, and record its model and prompt version.

## Planned validation

| Check | Expected behavior |
|---|---|
| Missing required site features | Flag insufficient information instead of assuming eligibility. |
| Incompatible network or run versions | Stop the affected analysis and identify the mismatch. |
| Unsupported treatment or effect estimate | Exclude it from quantitative benefit claims and record the reason. |
| Benefit calculation | Match a hand-checked example with explicit units and assumptions. |
| Memo evidence | Trace factual claims and treatment estimates to inputs or catalog sources. |
| Repeat run | Reproduce structured results using the same inputs, rules, and configuration; retain generated memo text for audit. |

Use synthetic fixtures first, then review representative real sites with the team. Record actual test results separately from this plan. S2's risk-model backtest does not establish the causal effectiveness of S3 recommendations.

## Interface decisions needed first

1. Agree on stable site IDs, network versions, S2 run selection, and risk units.
2. Confirm which road features and crash-pattern summaries S1 can provide, including their provenance and dates.
3. Define the initial treatment catalog, evidence acceptance rules, and candidate comparison method.
4. Agree with Kabir on S3 result tables, migrations, and database permissions. S3 needs an approved write path for its own outputs as well as read access to upstream data.
5. Agree with Juan on the structured recommendation and memo fields S4 will consume.
6. Confirm memo format, review criteria, and any numerical acceptance thresholds against the project baseline.

## Implementation sequence

1. Freeze a small input/output contract with S1, S2, and S4.
2. Build a small curated catalog and synthetic site fixtures.
3. Implement eligibility rules and test accepted, rejected, and missing-data cases.
4. Produce one traceable recommendation and template-based memo end to end.
5. Add supported benefit calculations and candidate comparisons.
6. Connect to approved database views and result tables.
7. Review real-site outputs, document limitations, and add LLM-assisted drafting if needed.

No runnable quickstart is included until the corresponding modules and dependencies exist.

## Boundaries

Kabir owns source ingestion, network construction, crash matching, feature production, and database schema. Param owns risk modeling, EB correction, severity modeling, network rankings, SHAP explanations, and the A/B/C backtest. Jose owns countermeasure tools and memos. Juan owns REST endpoints, website, deployment, and user-facing exports.

S3 exchanges subsystem data through IF-09 and does not read another owner's working files. Local artifacts support reproducibility and independent review. Schema changes must be coordinated with S1. Recommendations remain draft decision support pending engineering review.
