# Implemented frozen backtest protocol

Binding source: FSR 3.2.1.5-12 and 3.2.1.21; EVP 4.2. FSR takes precedence over older
research suggesting only 2017-2022. Default history is 2015-2022; configurable subsets are recorded.

1. Freeze and validate network, provenance, feature allowlist, source versions and availability.
   Reject post-2022 predictors, HIN/outcome features, duplicate records and unknown scope.
2. Fit B (locally calibrated NB2 SPF) and C (Poisson boosting) on the same site-history totals.
   Both use log(risk_length_mi * history years) as exposure offset. Summed historical predictions
   and counts share the same time scale. Estimate site-total k, then apply
   w=1/(1+k*mu), n_eb=w*mu+(1-w)*observed. U stays in total-crash labels but not severity labels.
3. Fit the same regularized binomial severity model for B/C. Diagnose calibration on 20% of
   held-out historical sites with separate train-only preprocessing; refit on all historical sites.
   Site expected F&SI/year=(n_eb/history years)*p_fsi. Divide by positive approved risk exposure.
4. Rank B/C with deterministic lexical site-ID ties. Flag a whole-site rank prefix nearest 11%
   of disjoint network-length allocation; reject if outside 10.5-11.5%. A remains published HIN.
5. Score 2023-2025 K/A crashes divided by all K/A crashes in the City area, retaining unmatched
   crashes. No events yields an explicitly undefined result, not a fabricated capture rate.
6. Resample individual test crashes with replacement at least 1,000 times. Use identical samples
   for methods and compute paired B-A/C-A differences. Report percentile 95% intervals.
7. Report 5% and 20% network shares, total-crash capture, and the actual HIN share for equal-length
   comparisons. A does not acquire an invented ranking at other shares. Record discrete rounding.
8. Store every result, artifact, calibration/explanation and BIT record. Exact replay verifies
   scores, ranks and backtest with frozen source/library versions. No superiority condition is used.

Intervals condition on fitted rankings and do not include training or road-cluster uncertainty.
In-sample ML dispersion may be optimistic. SHAP is for the ML log-count component before EB
and severity. City performance and reference-host resource constraints remain to be measured.
