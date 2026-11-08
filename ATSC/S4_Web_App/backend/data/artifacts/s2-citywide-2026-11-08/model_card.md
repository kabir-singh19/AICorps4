# Model card: s2-citywide-2026-11-08

S2 crash-risk ranking for College Station (S1 network v1_2022, 5,590 segments and 1,634 intersections).

## Methods (fixed in the config before the backtest)

- A: published MPO CSAP high-injury network (Fig. 3.9, digitized), membership from S1 `s2_hin_site`.
- B: NB2 safety performance function on KABC crashes with HSM empirical Bayes, times P(KA|KABC).
- C (primary, EVP 4.2): ML-EB. Poisson LightGBM on site features (no own crash history) for all crashes, EB blend with the site's last 5 years, times P(KABC|crash) and P(KA|KABC) (binomial GLMs shrunk toward the site's own history with 10 pseudo-crashes).
- Stack, LightGBM, LGB-Tot, Naive: the Nov 4 notebook models, reported for comparison only.

## Data and as-of dates

- Backtest: label years 2019-2022, crash history 2016-2022, features TxDOT inventory 2019 (available 2021-08-06), OSM and network as of 2022-12-31. Test: 2023-2025 crashes. The leakage gate refused every seeded post-cutoff record.
- Forecast 2026: refit on label years 2019-2025 with crash history through 2025-12-31; static features unchanged (no newer TxDOT snapshot is in S1).
- Ranking metric: expected K+A crashes per mile per year (`fsi_rate`); intersections use the 250 ft influence length (0.0473 mi) for both rate and flagging (ICD Table 9).

## Backtest (frozen 2022, 1,000 paired crash-level bootstrap resamples)

| Target | Budget | A | B | C | Stack | B-A | C-A | Stack-A |
|---|---|---|---|---|---|---|---|---|
| KA | 5pct (icd_250ft) | 0.795 [0.731, 0.854] | 0.579 [0.509, 0.655] | 0.585 [0.509, 0.661] | 0.602 [0.526, 0.673] | -0.216 [-0.281, -0.158] | -0.211 [-0.275, -0.146] | -0.193 [-0.257, -0.135] |
| KA | 11pct (icd_250ft) | 0.795 [0.731, 0.854] | 0.713 [0.643, 0.778] | 0.702 [0.632, 0.766] | 0.713 [0.643, 0.778] | -0.082 [-0.140, -0.023] | -0.094 [-0.146, -0.047] | -0.082 [-0.135, -0.029] |
| KA | 20pct (icd_250ft) | 0.795 [0.731, 0.854] | 0.778 [0.719, 0.836] | 0.789 [0.725, 0.848] | 0.795 [0.731, 0.854] | -0.018 [-0.070, +0.035] | -0.006 [-0.053, +0.047] | +0.000 [-0.047, +0.047] |
| KA | hin_share (icd_250ft) | 0.795 [0.731, 0.854] | 0.807 [0.743, 0.865] | 0.819 [0.760, 0.871] | 0.819 [0.760, 0.871] | +0.012 [-0.035, +0.064] | +0.023 [-0.018, +0.064] | +0.023 [-0.018, +0.070] |
| KA | hin_matched_counts (icd_250ft) | 0.795 [0.731, 0.854] | 0.784 [0.719, 0.842] | 0.807 [0.743, 0.860] | 0.813 [0.749, 0.865] | -0.012 [-0.053, +0.035] | +0.012 [-0.029, +0.053] | +0.018 [-0.023, +0.064] |
| KA | 11pct (s1_zero_length) | 0.795 [0.731, 0.854] | 0.743 [0.673, 0.807] | 0.766 [0.702, 0.825] | 0.760 [0.690, 0.825] | -0.053 [-0.111, +0.000] | -0.029 [-0.076, +0.018] | -0.035 [-0.082, +0.012] |
| KABC | 5pct (icd_250ft) | 0.794 [0.777, 0.812] | 0.662 [0.643, 0.684] | 0.672 [0.651, 0.694] | 0.673 [0.652, 0.696] | -0.132 [-0.149, -0.116] | -0.122 [-0.138, -0.106] | -0.121 [-0.137, -0.105] |
| KABC | 11pct (icd_250ft) | 0.794 [0.777, 0.812] | 0.760 [0.742, 0.780] | 0.781 [0.764, 0.800] | 0.781 [0.764, 0.800] | -0.034 [-0.049, -0.021] | -0.013 [-0.026, +0.000] | -0.013 [-0.025, +0.000] |
| KABC | 20pct (icd_250ft) | 0.794 [0.777, 0.812] | 0.822 [0.806, 0.840] | 0.831 [0.815, 0.848] | 0.831 [0.815, 0.848] | +0.029 [+0.015, +0.041] | +0.037 [+0.024, +0.049] | +0.037 [+0.025, +0.048] |
| KABC | hin_share (icd_250ft) | 0.794 [0.777, 0.812] | 0.839 [0.823, 0.857] | 0.848 [0.833, 0.864] | 0.848 [0.833, 0.864] | +0.046 [+0.033, +0.057] | +0.055 [+0.042, +0.067] | +0.054 [+0.042, +0.065] |
| KABC | hin_matched_counts (icd_250ft) | 0.794 [0.777, 0.812] | 0.819 [0.804, 0.836] | 0.831 [0.815, 0.847] | 0.831 [0.816, 0.847] | +0.026 [+0.014, +0.037] | +0.037 [+0.026, +0.050] | +0.038 [+0.026, +0.049] |
| KABC | 11pct (s1_zero_length) | 0.794 [0.777, 0.812] | 0.809 [0.793, 0.827] | 0.812 [0.795, 0.830] | 0.813 [0.797, 0.832] | +0.015 [+0.002, +0.027] | +0.018 [+0.005, +0.031] | +0.019 [+0.007, +0.032] |

Primary (KA, 11%): C flagged 0.1100 of network length, B 0.1100; test K+A crashes in the area 171.

## Calibration (2023-2025, matched crashes)

- SPF+EB: predicted/observed KA 0.74, KABC 1.01
- ML-EB: predicted/observed KA 0.74, KABC 1.01
- Stack: predicted/observed KA 0.90, KABC 1.24
- Severity P(KA|crash): Brier score 0.0358 on 4114 known-severity crashes

## Run facts

- Training and scoring time: 668 s (stages in manifest.json)
- Reload of saved models reproduced the ranking: True
- Independent refit reproduced the ranking hash: True
- Ranking hash: `044da876680fead6a269b8e524ad78af575848ffda386c75805928b778a874aa`
- BIT: 20/20 seeded faults detected, 0 false alarms in 20 clean refits (PASS)
- Forecast: 774 sites flagged (382 segments, 392 intersections), 0.1100 of network length

## Limits

- One city: 4 label years for the backtest fit. KA counts are small, so KA intervals are wide.
- No pedestrian/bicycle crash field in the delivered CRIS exports; no streetlight layer.
- AADT is missing on OSM-only streets; those take their functional-class median (flag `aadt_imputed`).
- Explanations are TreeSHAP of the ML-EB prior (site features); the EB history blend is reported separately as `eb_weight`, `ka_3y`, `kabc_3y`.
