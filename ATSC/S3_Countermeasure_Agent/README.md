S3 — Countermeasure Recommendations and Memos
- Owner: Jose, AI Corps Team 4
- Project: AI Traffic-Safety Consultant
- Status: Standalone College Station screening and memo prototype
- Updated: November 18, 2026
S3 takes a saved road-site snapshot, screens treatments against a reviewed countermeasure library, and produces a cited Markdown and HTML memo for engineering review. The team reported that all 15 final API drafts passed software validation. A separate offline replay of the same 15 site inputs also produced 15 passing reports and both memo formats.
Run one site
Use Python 3.9 or later. Run the commands from the S3 folder. The examples assume these filenames. If your downloads have numbered suffixes, rename them to the names below or supply the actual paths with --sites and --library.
- countermeasure_library.csv — Reviewed treatment records, CMFs, sources, study conditions and limitations
- countermeasure_matcher.py — Screens the library and explains each match or exclusion
- example_sites_s2_demo.json — Saved site inputs for the 15-site demonstration
- memo_pipeline.py — Builds the evidence, prepares or requests a draft, validates it and renders the memo
- test_matcher.py, test_memo_pipeline.py — Matcher and memo tests in the project test layout
Offline demo
Run the full workflow with locally generated summaries. This mode requires no API key.
python memo_pipeline.py --sites example_sites_s2_demo.json --site-id 17120 --mode offline
TAMU Chat API demo
In the shell or PyCharm run configuration, set MEMO_API_URL to the full HTTPS chat-completions endpoint supplied by the provider, MEMO_API_KEY to your local key, and MEMO_MODEL to an authorized model ID. The reported demo runs used protected.gpt-4.1. Keep credentials out of project files.
python memo_pipeline.py --sites example_sites_s2_demo.json --site-id 17120 --mode api
Each invocation creates a separate folder under runs/ and prints its path. Open memo.html to present the site or use the browser’s Print → Save as PDF. To investigate a blocked draft, open validation.json and compare its errors with the corresponding saved attempt.
How a site becomes a memo
1. Read the snapshot. Use the supplied site ID, site type, crash patterns, and available road, severity and lighting information. Preserve the crash observation window, S2 model/run details, risk estimates and contributing factors when supplied. Missing values remain unknown.
2. Screen the treatments. The matcher checks the location and study conditions it supports. It separates direct crash-type candidates from options with broader or partial evidence and records outstanding checks. An existing road attribute in the memo does not by itself establish that the matcher evaluated it.
3. Draft and validate. In API mode the model writes short treatment explanations. Python supplies the site summary and renders recorded numbers, CMFs and references from the evidence. The validator checks the structured response, expected treatment IDs and groups, and restrictions on free text. Failed API drafts can trigger correction calls.
4. Render the accepted draft. The memo presents the crash profile, available S2 assessment, treatment evidence, and engineering review items. Staff review the narrative, confirm site geometry and equipment, and decide whether any option warrants further study.
Example — F&B Road at FM 2818, site 17120. The saved snapshot records 26 crashes during 2023–2025, including 13 rear-end and 7 angle crashes. S3 returned zero direct crash-type candidates and six options for engineering review. One option, CM016, concerns conversion to a Type B median U-turn. Its cited CMF covers injury severities A, B and C combined. Applying that value to the site’s predicted fatal and serious-injury crashes would exceed the study’s scope.
Evidence and run files
The current CSV contains 30 entries. Of those, 28 have distinct CMF Clearinghouse IDs and are marked clearinghouse_record_verified and reviewed for original-study review. The two process entries are Road Safety Audit (CM022) and Local Road Safety Plans (CM024). Neither has a numerical CMF. Site applicability remains a separate engineering decision. FHWA CMF Clearinghouse · FHWA Proven Safety Countermeasures
- evidence.json — Site inputs, matched library records, study scopes and review conditions
- structured_prompt.txt — Instructions and evidence supplied for the draft
- response_attempt_1.txt, etc. — Individual API responses, including attempts blocked before correction
- response.json — Accepted structured draft used for rendering
- memo.md, memo.html — Human-readable outputs after the contract checks pass
- validation.json — Final status, errors by attempt, evidence/output hashes and available API usage and timing
Validation results and limits
- Real-site API demonstration — Team-reported result of 15/15 final drafts passing. Seven sites needed automatic correction.
- Offline reproducibility — All 15 saved site inputs passed the software checks and produced Markdown and HTML in the November 18 replay.
- Correction example — For site 17120, two saved API attempts included digits in the CM034 narrative. The validator flagged both. The third attempt passed.
- Seeded response checks — The supplied memo unit test defines 20 mixed contract violations, including wrong IDs, unexpected fields and prohibited numeric text. A dedicated 20-case invented-number result requires its own test evidence.
- Citation handling — Python renders citations from matched library records. The memo tests check that source URLs, study references and limitations survive rendering. A seeded missing-citation blocking result requires a test of that failure.
- Engineering quality and cost — Blind review against professional reference memos is planned. The API logs expose timing and token usage when supplied. The team reported a zero TAMU charge for the demo. The saved run’s dollar-cost field can be null.
Run the existing tests from the project layout with its fixtures available. The supplied memo suite reads example_sites.json and fixtures/countermeasure_library_2026-11-03.csv.
python -m unittest -v test_matcher
python -m unittest -v test_memo_pipeline
A passing report marks the draft ready for human review. The checks do not establish the truth of every narrative claim, a site-specific crash reduction, or approval to install a treatment.
Integration and next steps
The standalone demonstration uses saved snapshots. The project interface baseline is Team4_AI_Traffic_Safety_Consultant_ConOps_FSR_ICD_EVP 2-1.pdf, ConOps Revision C, October 1, 2026.
- S1 → S3 — Confirm stable site IDs, network version, road features, crash definitions and provenance.
- S2 → S3 — Confirm run IDs, risk units, severity definitions and explanatory factors against the live interface.
- S3 → S4 — Agree on the machine-readable handoff for draft status, treatment IDs, citations and unresolved checks.
- S3 ↔ IF-09 — Confirm approved database read/write paths with the owning subsystem.
For benefit/cost analysis, verify the treatment layout, baseline crash units, applicable CMF, installation cost, service life and analysis period. Keep treatment installation cost separate from the API cost of writing a memo. The current standalone workflow does not calculate numerical benefits or rank treatments by benefit. S2 factors explain model predictions and do not establish the cause of crashes.

The planned 15-site blind review will compare draft quality against professional references. Recording reviewer editing time alongside API usage would also help evaluate the project’s goal of producing comparable memos at lower preparation cost.
