# Model card: s2-citywide-v1.1-2026-11-08

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
| KA | 5pct (icd_250ft) | 0.795 [0.731, 0.854] | 0.591 [0.520, 0.661] | 0.585 [0.509, 0.661] | 0.585 [0.509, 0.655] | -0.205 [-0.269, -0.140] | -0.211 [-0.275, -0.146] | -0.211 [-0.275, -0.146] |
| KA | 11pct (icd_250ft) | 0.795 [0.731, 0.854] | 0.708 [0.632, 0.772] | 0.696 [0.626, 0.760] | 0.708 [0.637, 0.772] | -0.088 [-0.146, -0.029] | -0.099 [-0.152, -0.047] | -0.088 [-0.140, -0.035] |
| KA | 20pct (icd_250ft) | 0.795 [0.731, 0.854] | 0.778 [0.719, 0.836] | 0.784 [0.719, 0.842] | 0.784 [0.719, 0.842] | -0.018 [-0.070, +0.035] | -0.012 [-0.058, +0.035] | -0.012 [-0.058, +0.035] |
| KA | hin_share (icd_250ft) | 0.795 [0.731, 0.854] | 0.795 [0.731, 0.854] | 0.807 [0.749, 0.860] | 0.813 [0.754, 0.871] | +0.000 [-0.041, +0.053] | +0.012 [-0.029, +0.058] | +0.018 [-0.023, +0.064] |
| KA | hin_matched_counts (icd_250ft) | 0.795 [0.731, 0.854] | 0.784 [0.719, 0.842] | 0.801 [0.737, 0.854] | 0.807 [0.743, 0.860] | -0.012 [-0.053, +0.035] | +0.006 [-0.035, +0.053] | +0.012 [-0.029, +0.058] |
| KA | 11pct (s1_zero_length) | 0.795 [0.731, 0.854] | 0.743 [0.673, 0.807] | 0.754 [0.690, 0.819] | 0.749 [0.678, 0.807] | -0.053 [-0.111, +0.000] | -0.041 [-0.094, +0.012] | -0.047 [-0.099, +0.000] |
| KABC | 5pct (icd_250ft) | 0.794 [0.777, 0.812] | 0.658 [0.638, 0.679] | 0.668 [0.647, 0.691] | 0.667 [0.646, 0.691] | -0.136 [-0.153, -0.120] | -0.126 [-0.142, -0.110] | -0.126 [-0.142, -0.111] |
| KABC | 11pct (icd_250ft) | 0.794 [0.777, 0.812] | 0.755 [0.738, 0.775] | 0.774 [0.758, 0.793] | 0.776 [0.760, 0.795] | -0.038 [-0.052, -0.025] | -0.019 [-0.033, -0.007] | -0.017 [-0.031, -0.005] |
| KABC | 20pct (icd_250ft) | 0.794 [0.777, 0.812] | 0.818 [0.801, 0.836] | 0.830 [0.814, 0.847] | 0.829 [0.813, 0.846] | +0.024 [+0.011, +0.037] | +0.036 [+0.023, +0.048] | +0.035 [+0.023, +0.047] |
| KABC | hin_share (icd_250ft) | 0.794 [0.777, 0.812] | 0.837 [0.821, 0.855] | 0.847 [0.831, 0.862] | 0.844 [0.829, 0.860] | +0.044 [+0.031, +0.055] | +0.053 [+0.040, +0.065] | +0.050 [+0.038, +0.061] |
| KABC | hin_matched_counts (icd_250ft) | 0.794 [0.777, 0.812] | 0.818 [0.802, 0.834] | 0.828 [0.812, 0.845] | 0.831 [0.815, 0.847] | +0.024 [+0.013, +0.036] | +0.034 [+0.023, +0.047] | +0.038 [+0.026, +0.050] |
| KABC | 11pct (s1_zero_length) | 0.794 [0.777, 0.812] | 0.800 [0.784, 0.818] | 0.802 [0.785, 0.819] | 0.806 [0.790, 0.825] | +0.007 [-0.006, +0.019] | +0.008 [-0.005, +0.021] | +0.013 [+0.000, +0.025] |

Primary (KA, 11%): C flagged 0.1099 of network length, B 0.1100; test K+A crashes in the area 171.

## Calibration (2023-2025, matched crashes)

- SPF+EB: predicted/observed KA 0.74, KABC 1.01
- ML-EB: predicted/observed KA 0.74, KABC 1.01
- Stack: predicted/observed KA 0.90, KABC 1.24
- Severity P(KA|crash): Brier score 0.0358 on 4114 known-severity crashes

## Run facts

- Training and scoring time: 753 s (stages in manifest.json)
- Reload of saved models reproduced the ranking: True
- Independent refit reproduced the ranking hash: True
- Ranking hash: `875ded04c67aa6044148e5150a1c6eebfab4070cf3292c83bd7dd6eeb1d369cc`
- BIT: 20/20 seeded faults detected, 0 false alarms in 20 clean refits (PASS)
- Forecast: 746 sites flagged (364 segments, 382 intersections), 0.1100 of network length

## Limits

- One city: 4 label years for the backtest fit. KA counts are small, so KA intervals are wide.
- No pedestrian/bicycle crash field in the delivered CRIS exports; no streetlight layer.
- AADT is missing on OSM-only streets; those take their functional-class median (flag `aadt_imputed`).
- Explanations are TreeSHAP of the ML-EB prior (site features); the EB history blend is reported separately as `eb_weight`, `ka_3y`, `kabc_3y`.
