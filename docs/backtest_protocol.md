# Frozen backtest protocol
Source: Execution and Validation Plan Section 4.2, FSR 3.2.1.5-12 and 3.2.1.21, and repository AITRAFFIC.md.

## 1. Freeze and validate
Record source versions/hashes, network and feature-set versions, analysis boundary, code version, seed, and hyperparameters. Information cutoff: **31 December 2022**. Baseline fitting/history window: **2017-2022**, as specified in AITRAFFIC.md and matching the consultant window. S1 ingests 2015-2025; any use of 2015-2016 for prior-year lags must be agreed and recorded.

Reject post-cutoff or unproven input information. Earlier-year training rows must use only appropriate prior-year crash-history features. Fit preprocessing, hyperparameters, and severity models using training-period data only. Reserve **2023-2025** crashes for final scoring, including sensitivity analysis; never use them to select models or thresholds.

## 2. Produce comparable methods
- **A:** published consultant HIN membership; retain its actual network-length share. Do not invent a continuous consultant ranking if only a flagged GIS layer is available.
- **B:** negative binomial safety performance function with EB.
- **C:** Poisson gradient-boosted crash-count prediction, estimated overdispersion, EB, and a calibrated severity model.

For EB, sum expected and observed counts over consistent history years:
w = 1 / (1 + k * sum(mu)); n_eb = w * sum(mu) + (1 - w) * sum(observed).
Annual expected F&SI = (n_eb / number_of_history_years) * p_fsi.
Divide by agreed site length in miles for ranking.

Use the same frozen sites and data availability rules for every method. Explain method B's severity conversion explicitly so its target matches C's. Provide a prediction for zero-crash sites. Rank B/C by F&SI per mile per year, use a documented deterministic tie rule, and flag cumulative length at 11% +/- 0.5 percentage points. Resolve intersection exposure with S1 first.

## 3. Score and quantify uncertainty
Capture = test-window F&SI crashes on flagged sites / all test-window F&SI crashes in the analysis area (KABCO K or A).
Count unique crashes once; report unmatched/out-of-network records and retain them in the area denominator where applicable. Do not silently replace this denominator with matched crashes only. If the denominator is zero, report the result as undefined rather than fabricating a rate.

Resample test F&SI crashes with replacement **1,000 times** using the same sample indices for A, B, and C. Recompute capture and paired differences C-A and B-A. Report 2.5th/97.5th percentiles as 95% intervals, alongside test count and flagged miles.

## 4. Fairness and sensitivity
If HIN's actual share differs from 11%, also score B/C at exactly that share (record discrete-site rounding). Repeat scoring at 5% and 20% network length and using total crashes instead of F&SI. A remains the published HIN unless an authentic published ranking supports other thresholds; clearly identify comparisons that cannot be made.

## 5. Publish evidence
Store A/B/C metrics, paired differences, uncertainty, calibration, SHAP explanations, sensitivity findings, and timing with the frozen run. Report results that favor HIN as well as those that favor EB/ML. Model superiority is a goal, not a condition for publishing the evidence. Replay must reproduce the ranking exactly.
