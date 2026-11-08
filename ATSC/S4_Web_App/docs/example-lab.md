# Example model and report

Open **Example lab** in the website, or add `?example=1` to the website URL. This page is always available without university credentials and does not depend on published model runs.

## Working example model

The demonstration uses a logistic-regression classifier trained on synthetic data. Four inputs are normalized to their allowed ranges: posted speed, daily vehicle volume, travel lanes, and pedestrian crossing locations per mile. The saved learned weights and intercept produce a synthetic review score between 0 and 1. The illustrative review threshold is 0.50.

The training generator uses seed 42 to create 500 artificial records. Labels come from an invented relationship plus random sampling. Four hundred records are used to fit the classifier; 100 are held out. These are not observations from College Station, TAMU, TxDOT, or any crash database. Synthetic holdout results do not establish real-world accuracy or safety value.

Change a preset's inputs and select **Run example model**. Changing an input clears the preceding result until a new score is computed. The model does not call an LLM or official university API. It requires no additional Python ML packages at runtime.

- Trained artifact: `backend/app/data/example-model.json`.
- Training source: `backend/scripts/train_example_model.py`. From `backend/`, run `.venv/bin/python scripts/train_example_model.py` to reproduce the artifact.
- Serving and report generation: `backend/app/examples.py`.
- UI: `frontend/src/components/ExampleLab.jsx`.

The score is not a calibrated crash probability, F&SI rate, causal effect, or intervention recommendation. This model demonstrates the prediction flow while the team's real risk model is integrated.

## Example report

The report computes scores for four fixed, invented scenarios named after University Drive, Harvey Road, Texas Avenue, and Wellborn Road. It includes a summary, relative ranking, input table, method, interpretation, next steps, and provenance. The road names are real; the attributes and rankings are synthetic. Editing the interactive model form does not rewrite this fixed report.

**Open printable report** opens an HTML document. Use the browser's Print menu to print or save as PDF. **Download example report** downloads the same report as HTML. The report is a deterministic template, not a generated university-AI answer or a published engineering memo. No fabricated external references or real model-performance claims are included.

The example endpoints are:

- `GET /api/v1/examples`: model card, fictional scenarios, predictions, and report text.
- `POST /api/v1/examples/predict`: bounded input validation and a fresh prediction.
- `GET /api/v1/examples/report.html`: printable document; add `?download=true` for attachment download.

The example routes do not write files, call paid services, or publish results into `/api/v1/runs`. The Example lab routes themselves do not change published data. Separately, two bundled `example-dashboard-*.json` fixtures populate the main runs, memos, and backtest tabs at the user’s request. Their invented F&SI rates and A/B/C tables are independent interface examples, not outputs of this logistic classifier. The Docker image already copies the artifact with `backend/app`; retraining is not performed during deployment.
