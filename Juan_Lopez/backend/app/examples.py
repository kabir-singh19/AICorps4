"""An offline, explicitly synthetic ML demonstration and reproducible sample report."""
import html
import json
import math
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/v1/examples", tags=["Synthetic example lab"])
DISCLAIMER = "Synthetic demonstration only. Road names are real, but all input values and results below are invented. This model is not trained or validated on Texas A&M, TxDOT, or real crash data. Scores are not crash probabilities, F&SI rates, or engineering recommendations."


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    speed_mph: float = Field(ge=20, le=65)
    daily_vehicles: int = Field(ge=1000, le=60000, strict=True)
    lanes: int = Field(ge=2, le=8, strict=True)
    crossings_per_mile: float = Field(ge=0, le=12)


SCENARIOS = [
    {"site_id": "demo-university", "road_name": "University Drive", "inputs": {"speed_mph": 45, "daily_vehicles": 42000, "lanes": 6, "crossings_per_mile": 8}},
    {"site_id": "demo-harvey", "road_name": "Harvey Road", "inputs": {"speed_mph": 35, "daily_vehicles": 18000, "lanes": 4, "crossings_per_mile": 4}},
    {"site_id": "demo-texas", "road_name": "Texas Avenue", "inputs": {"speed_mph": 50, "daily_vehicles": 48000, "lanes": 6, "crossings_per_mile": 6}},
    {"site_id": "demo-wellborn", "road_name": "Wellborn Road", "inputs": {"speed_mph": 40, "daily_vehicles": 24000, "lanes": 4, "crossings_per_mile": 3}},
]


@lru_cache
def model():
    return json.loads((Path(__file__).parent / "data" / "example-model.json").read_text())


def predict(scenario):
    spec = model()
    values = scenario.model_dump()
    normalized = [(values[feature["key"]] - feature["min"]) / (feature["max"] - feature["min"]) for feature in spec["features"]]
    terms = [weight * value for weight, value in zip(spec["weights"], normalized)]
    score = 1 / (1 + math.exp(-(spec["intercept"] + sum(terms))))
    return {"is_demo": True, "model_id": spec["model_id"], "inputs": values, "score": round(score, 6), "flagged": score >= spec["threshold"], "threshold": spec["threshold"], "score_unit": "Synthetic review score (0–1)", "contributions": [{"feature": feature["key"], "label": feature["label"], "logit_contribution": round(term, 6)} for feature, term in zip(spec["features"], terms)], "disclaimer": DISCLAIMER}


def report():
    sites = [{**site, "prediction": predict(Scenario(**site["inputs"]))} for site in SCENARIOS]
    sites.sort(key=lambda site: site["prediction"]["score"], reverse=True)
    for rank, site in enumerate(sites, 1):
        site["rank"] = rank
    count = sum(site["prediction"]["flagged"] for site in sites)
    return {"report_id": "example-corridor-report-v1", "title": "College Station corridor screening — example report", "is_demo": True, "disclaimer": DISCLAIMER, "model": model(), "sites": sites, "summary": f"The demonstration screened four fictional road scenarios. {count} of 4 exceed the illustrative 0.50 review threshold. Ranking is relative to these four scenarios only.", "method": "A logistic regression classifier was fitted to 400 synthetic training records, with 100 separate synthetic holdout records. It uses speed, daily vehicle volume, lane count, and crossing density. The threshold was chosen for this teaching example; it is not an engineering standard.", "interpretation": "A higher score means the inputs resemble the generated training examples labeled for review. It does not estimate the chance of a crash. Feature contributions describe this toy model's calculation, not causal effects on road safety.", "next_steps": ["Replace the invented inputs with approved, measured corridor attributes.", "Train and evaluate the team's risk model on the agreed real dataset and exposure definition.", "Review real findings with a qualified traffic engineer before proposing treatments.", "Publish validated results through the model adapter; keep AI explanations and engineering approval separate."], "provenance": ["Model artifact: synthetic-logistic-v1; training generator seed 42.", "Source of all scenario attributes: invented example values bundled with this application.", "Report text: deterministic application template; no university AI or language-model call."]}


@router.get("")
def example_report():
    return report()


@router.post("/predict")
def example_predict(body: Scenario):
    return predict(body)


def report_html(data):
    escape = lambda value: html.escape(str(value))
    rows = "".join(f'<tr><td>{site["rank"]}</td><th>{escape(site["road_name"])}</th><td>{site["prediction"]["score"]:.3f}</td><td>{"Review" if site["prediction"]["flagged"] else "Below demo threshold"}</td></tr>' for site in data["sites"])
    inputs = "".join(f'<tr><th>{escape(site["road_name"])}</th>' + "".join(f'<td>{escape(site["inputs"][feature["key"]])}</td>' for feature in data["model"]["features"]) + '</tr>' for site in data["sites"])
    headings = "".join(f'<th>{escape(feature["label"])} ({escape(feature["unit"])})</th>' for feature in data["model"]["features"])
    steps = "".join(f'<li>{escape(step)}</li>' for step in data["next_steps"])
    provenance = "".join(f'<li>{escape(item)}</li>' for item in data["provenance"])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Example corridor screening report</title>
<style>body{{font:16px/1.65 system-ui,sans-serif;color:#192d29;max-width:920px;margin:40px auto;padding:0 24px}}h1{{line-height:1.2}}.example{{border:2px solid #b87920;background:#fff7e9;padding:18px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{text-align:left;border-bottom:1px solid #bbc8c1;padding:10px}}.scroll{{overflow-x:auto}}@media print{{body{{margin:0}}h2{{break-after:avoid}}tr{{break-inside:avoid}}}}</style>
<p>ATSC · Texas A&amp;M student capstone · SAMPLE REPORT</p><h1>{escape(data["title"])}</h1><p class="example">{escape(data["disclaimer"])}</p><h2>Summary</h2><p>{escape(data["summary"])}</p>
<h2>Example model results</h2><div class="scroll"><table><caption>Synthetic review scores; these are not crash probabilities.</caption><thead><tr><th>Rank</th><th>Road scenario</th><th>Score (0–1)</th><th>Demo status</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Invented inputs</h2><div class="scroll"><table><thead><tr><th>Road scenario</th>{headings}</tr></thead><tbody>{inputs}</tbody></table></div>
<h2>Method</h2><p>{escape(data["method"])}</p><h2>Interpretation</h2><p>{escape(data["interpretation"])}</p><h2>Next steps for real integration</h2><ol>{steps}</ol><h2>Provenance</h2><ul>{provenance}</ul><p>Report ID: {escape(data["report_id"])} · Model: {escape(data["model"]["model_id"])}. No real backtest or validated safety benefit is claimed.</p></html>'''


@router.get("/report.html")
def download_report(download: bool = False):
    headers = {"Content-Disposition": 'attachment; filename="atsc-example-report.html"'} if download else {}
    return HTMLResponse(report_html(report()), headers=headers)
