# S3 - Countermeasure Recommendations and Memos

Owner: Jose | AI Corps Team 4 | AI Traffic-Safety Consultant

**Status: prototype v0.2 using synthetic site data.** The current work includes a countermeasure library, an initial CMF evidence pass, and a Python matcher that returns candidate treatments with reasons and remaining applicability checks. Database integration, numerical benefit estimates, candidate scoring, and memo generation remain future work.

## Purpose

S3 identifies possible safety improvements for a site's crash pattern and location type. Each candidate should explain why it matches, identify its supporting evidence, and flag information that still needs review.

The prototype can be developed independently while S1 and S2 finalize their data interfaces. Its synthetic examples do not establish effectiveness at real College Station sites.

## Current implementation

| Component | Current status |
| --- | --- |
| Countermeasure library | 24 treatment and process entries in `countermeasure_library.csv`. |
| CMF evidence | Initial pass recorded 22 CMFs, record IDs, source links, and study conditions. There are 21 star ratings and one officially unrated record. |
| Process entries | Road Safety Audits and Local Road Safety Plans have no standalone CMF assigned in this library. Their benefits require treatment-specific evidence. |
| Python matcher | Returns possible countermeasures, match reasons, and outstanding applicability checks using CMF-specific crash types. |
| Synthetic examples | Six example sites and saved results were included in the v0.2 package. |
| Tests | The v0.2 package was reported to pass 12 tests, including crash-type and lighting-condition checks. |

These implementation and test details describe the previously prepared v0.2 package. They have not been independently rerun for this README update and do not confirm which files have been committed to GitHub.

## Working files

| File | Responsibility |
| --- | --- |
| `countermeasure_library.csv` | Countermeasure descriptions, CMF evidence, study conditions, and limitations. |
| `countermeasure_matcher.py` | Match site crash patterns and location types to candidate treatments with reasons. |
| `test_matcher.py` | Check matching behavior and safeguards using synthetic inputs. |
| `README.md` | Explain the prototype, how to run it, its limitations, and next steps. |

The v0.2 package also contains synthetic examples and saved results. Keep those alongside the matcher according to the package's existing layout.

## Run the prototype

From the extracted v0.2 folder containing the matcher, library, and tests:

```bash
python countermeasure_matcher.py
python -m unittest -v test_matcher.py
```

The first command runs the prototype's included examples. The second runs its tests. Upload the corresponding package files together before using these commands from a repository checkout.

## Current workflow

1. Read a synthetic site's crash pattern, location type, and available conditions.
2. Compare those inputs with the countermeasure library and CMF-specific applicability rules.
3. Return candidate treatments with reasons they match.
4. Identify evidence limitations and site conditions that still need checking.

The output is a list of candidates for review. It is not a final design recommendation or a numerical prediction of crash reduction.

## CMF evidence status

**CMF verification remains open.** The initial evidence pass used indexed FHWA CMF Clearinghouse records because live detail pages returned errors. Direct record review and site-specific applicability checks are still needed before quantitative use.

Evidence sources:

- [FHWA CMF Clearinghouse](https://cmfclearinghouse.fhwa.dot.gov/)
- [FHWA Proven Safety Countermeasures](https://highways.dot.gov/safety/proven-safety-countermeasures)

The matcher must respect the specific treatment, crash type, severity, roadway context, and conditions covered by each record. A pedestrian-only CMF cannot support an angle-crash benefit claim. A nighttime CMF cannot support a daytime benefit claim. Evidence for a package of improvements cannot automatically be credited to one component.

**Numerical crash-reduction estimates are disabled in this prototype.** A recorded CMF does not mean it has been approved for a particular site or for fatal and serious-injury outcomes.

## Validation and limitations

The reported 12-test run includes checks that pedestrian-only CMFs do not match angle crashes and daytime examples do not receive a nighttime lighting CMF. These checks demonstrate selected matching safeguards; they do not validate real-world safety benefits.

Remaining checks include missing or unknown site features, unsupported crash types, incompatible location types, and cases where no suitable candidate exists. Missing information should remain visible rather than being treated as proof of eligibility.

No real-site validation, S1/S2 database connection, benefit/cost analysis, candidate ranking method, or memo-generation workflow is claimed by this version.

## Next steps

1. **Document the current input and output format.** Use one synthetic example to define required fields, allowed crash and location types, missing-value handling, and returned candidate fields.
2. **Review matching behavior.** Check accepted, rejected, missing-data, and no-match cases. Keep match reasons and unresolved conditions visible.
3. **Complete evidence review.** Revisit the original Clearinghouse records and confirm treatment definitions, crash types, severity, quality ratings, and study conditions.
4. **Agree on integration fields.** Coordinate stable site IDs, network versions, crash-pattern summaries, S2 run IDs, and risk units with the subsystem owners.
5. **Connect a representative real site.** Review its candidates and evidence with the team before expanding the workflow.
6. **Add later capabilities when their inputs are ready.** Candidate comparison, supported benefit calculations, database persistence, and draft memos follow the matching and interface work.

## Integration plan

The project baseline is **Team4_AI_Traffic_Safety_Consultant_ConOps_FSR_ICD_EVP 2-1.pdf**, ConOps Revision C dated 1 October 2026, with its accompanying FSR, ICD, and Execution and Validation Plan. Confirm interface details against that baseline before implementation.

| Direction | Information to agree with the owning subsystem |
| --- | --- |
| S1 → S3 | Stable site ID, network version, location type, road features, crash-pattern summaries, and provenance. |
| S2 → S3 | Model/run ID, site-linked risk results, severity definitions, units, flags, and available explanations. |
| S3 → S4 | Candidate treatments, match reasons, evidence references, unresolved conditions, and review status; memo fields later. |
| S3 ↔ IF-09 | Approved upstream read access and an agreed write path for S3 results. |

These are integration needs, not confirmed database columns or implemented connections. Coordinate schema changes and write permissions with S1, and output fields with S4.

## Rules for future numerical recommendations

- Use a CMF only when its treatment, outcome, severity, road context, and study conditions support the analysis.
- Align baseline units and time periods. A per-mile risk rate is not an annual site crash count.
- Treat SHAP factors as explanations of model predictions, not causal evidence for a treatment.
- Do not automatically multiply CMFs for combined treatments.
- Leave unavailable costs and effect estimates unknown. Add benefit/cost calculations only with sourced costs and agreed assumptions.
- Keep rules, evidence versions, and calculations reproducible. Draft memos must trace their claims to reviewed inputs and sources.

