# Model card status

No City model has been trained. Each completed user-run bundle automatically writes
model_card.md with run/code/data identity, split, method captures and paired intervals,
calibration status, timing and limitations. Calibration.json/SVG and backtest.json provide the
underlying evidence. Synthetic fixtures are labeled explicitly.

Review historical availability, City scope, intersection exposure, unknown-severity missingness,
static feature dates, in-sample overdispersion, calibration sample size, whole-site length rounding,
crash-level bootstrap assumptions and model-component SHAP before using a production result.
Qualified traffic engineering review and reference-host validation remain necessary handoff work.
