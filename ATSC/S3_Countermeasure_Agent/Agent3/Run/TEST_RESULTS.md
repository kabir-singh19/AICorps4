# Local verification

Command: `python -m unittest -v test_memo_pipeline test_matcher`

Result: 40 tests passed (33 existing matcher tests and 7 new memo-pipeline tests).
One new test exercises 20 independently corrupted response objects and confirms each
is rejected by the response-contract validator. These are not twenty full memo reviews.

Additional checks:

- Offline CLI generated a memo for SYN001_PEDESTRIAN_SIGNAL with three direct
  candidates and five engineering-review options.
- Validation report: contract_checks_passed=true, semantic_grounding_verified=false,
  human_review_required=true, engineering_approval=false.
- Tests confirm preservation of all supplied review conditions, source URLs, study
  references and evidence limitations in the rendered memo.
- API request/response handling tested with a mock only. No live API request was made.
- A deliberate qualitative overclaim passes the structural validator; this known limit
  is tested and documented, and human review remains mandatory.

Not verified: live TAMU access, original studies, runtime/cost targets, full semantic
grounding, engineering applicability, benefit/cost estimates or final subsystem acceptance.
