# CMF evidence audit — 21 October 2026

## Result and limits

The original 22 numerical entries were cross-checked against retrieved official Clearinghouse indexed records. No discrepancies were found in the stored CMF values, severity labels, standard errors or rating points. The two process entries were cross-checked against FHWA guidance and retain blank numerical CMFs.

This completes an indexed-record audit, not full evidence verification. Direct live retrieval failed for sampled pages; indexed copies range from days to over a year old. Every original study still requires review, and site applicability remains pending. The 3357 and 9200 retrieved copies were approximately one year old. No entry is approved for numerical benefit calculation.

## Changes

- Clarified CM003 treatment wording to include crossings with or without marked crosswalks.
- Clarified CM020 wording to include illuminance and uniformity; retained the exact lighting-level contrast and nighttime condition.
- Clarified CM010: the outcome is single-vehicle run-off-road crashes, not either label independently.
- Added original-study review flags for the potentially combined crash outcomes in CM007, CM008 and CM014.
- Added explicit record-check, original-study-review and rating-basis columns. Existing matcher categories and numerical values are preserved.

## Entry-by-entry record checks

“Matches” below means the stored scalar, severity, setting and rating agree with the retrieved record. Conditions are summarized in the existing CSV. No original study was independently reviewed in this pass.

| Entry | CMF record | Value | Stars | Record check / remaining issue |
|---|---|---:|---:|---|
| CM001 | [4123](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=4123) | 0.6 | 2 | Matches. Live freshness, original study and site applicability pending. |
| CM002 | [9918](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=9918) | 0.87 | 5 | Matches. Live freshness, original study and site applicability pending. |
| CM003 | [8799](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=8799) | 0.685 | 4 | Matches. Live freshness, original study and site applicability pending. |
| CM004 | [9020](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=9020) | 0.453 | 3 | Matches. Live freshness, original study and site applicability pending. |
| CM005 | [9024](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=9024) | 0.526 | 3 | Matches. Live freshness, original study and site applicability pending. |
| CM006 | [1333](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=1333) | 0.26 | — | Matches. Officially unrated; retain blank star rating. Original study and site applicability pending. |
| CM007 | [2437](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=2437) | 0.94 | 4 | Matches. Listed crash types include Non-intersection. Confirm the combined crash definition in the original study before applying the scalar to an individual subtype. |
| CM008 | [3357](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=3357) | 0.55 | 5 | Matches. Confirm whether the estimate combines head-on and sideswipe crashes and whether sideswipes are opposite-direction before subtype-specific numerical use. |
| CM009 | [5445](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=5445) | 0.35 | 2 | Matches. Live freshness, original study and site applicability pending. |
| CM010 | [4130](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=4130) | 0.1 | 3 | Matches. The comments specify single-vehicle run-off-road crashes, a combined condition. Neither label alone establishes applicability. |
| CM011 | [9200](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=9200) | 0.842 | 4 | Matches. Live freshness, original study and site applicability pending. |
| CM012 | [4737](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=4737) | 0.635 | 4 | Matches. Live freshness, original study and site applicability pending. |
| CM013 | [1410](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=1410) | 0.85 | 4 | Matches. Live freshness, original study and site applicability pending. |
| CM014 | [2514](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=2514) | 0.77 | 4 | Matches. The record lists multiple crash types. Confirm the modeled outcome in the original study before applying the scalar to any one subtype. |
| CM015 | [267](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=267) | 0.72 | 4 | Matches. Live freshness, original study and site applicability pending. |
| CM016 | [10867](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=10867) | 0.7029 | 5 | Matches. Live freshness, original study and site applicability pending. |
| CM017 | [226](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=226) | 0.22 | 3 | Matches. Live freshness, original study and site applicability pending. |
| CM018 | [8867](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=8867) | 0.899 | 4 | Matches. Live freshness, original study and site applicability pending. |
| CM019 | [380](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=380) | 0.92 | 2 | Matches. Live freshness, original study and site applicability pending. |
| CM020 | [11026](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=11026) | 0.679 | 4 | Matches. Live freshness, original study and site applicability pending. |
| CM021 | [10319](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=10319) | 0.49 | 5 | Matches. Live freshness, original study and site applicability pending. |
| CM022 | [FHWA guidance](https://highways.dot.gov/safety/proven-safety-countermeasures/road-safety-audit) | — | — | Process guidance checked; no scalar selected. |
| CM023 | [11230](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=11230) | 0.71 | 3 | Matches. Live freshness, original study and site applicability pending. |
| CM024 | [FHWA guidance](https://highways.dot.gov/safety/proven-safety-countermeasures/local-road-safety-plans) | — | — | Process guidance checked; no scalar selected. |

## Rating method

Where indexed pages omit star images, stars are derived from posted points using the official [rating crosswalk](https://cmfclearinghouse.fhwa.dot.gov/newsletter/2020Q4.html): 0–34 = 1, 35–74 = 2, 75–109 = 3, 110–134 = 4, 135–150 = 5. CM006 explicitly says Cannot Be Rated and remains blank.

## Remaining verification work

1. Check live records or downloaded official exports for changes since indexing, especially CMFs 3357 and 9200.
2. Review original papers for combined crash definitions, treatment prerequisites, comparison groups and applicability. Prioritize CM007, CM008, CM010 and CM014.
3. Supply actual geometry, traffic volumes and existing treatments before approving a site match.
4. Keep benefit calculations disabled. Automated tests confirm software behavior, not engineering validity.

The broad crash_types column contains discovery tags. cmf_crash_types and study restrictions govern evidence scope. Some site_type labels are implementation mappings rather than verbatim source fields; they still require original-study validation.

## Expansion: CM025–CM029

Five distinct interventions added on 21 October 2026. Total: 29 entries (27 numerical records and two processes). Each new entry was checked against an official indexed detail record for ID, value, crash and severity scope, setting, standard error and rating points. Live freshness and original-study review remain pending. The previous 22-entry audit above remains the baseline.

| Entry | Treatment | Record | CMF | Stars | Key limit |
|---|---|---|---:|---:|---|
| CM025 | Install shoulder rumble strips | [3454](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=3454) | 0.64 | 5 | Empirical Bayes study in MN, MO and PA. KABC includes minor and possible injury; not KA-only. Does not represent centerline rumble strips. Detailed shoulder prerequisites require original-study review. |
| CM026 | Install pedestrian countdown timer | [10119](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=10119) | 0.912 | 4 | Empirical Bayes estimate from 333 sites. Approximate CMF +/- 1.96 SE interval includes 1.0. Does not establish a guaranteed pedestrian-crash reduction or an effect on every crash type. |
| CM027 | Convert minor-road stop control to all-way stop control | [315](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=315) | 0.52 | 2 | Simple before-after. Adjusted SE 0.04. Aggregate crash scope; not an angle-only CMF. Control warrants, operations and source geometry require engineering review. |
| CM028 | Install transverse rumble strips on rural stop-controlled approaches | [2708](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=2708) | 0.987 | 3 | Empirical Bayes study in Iowa and Minnesota. KABC combined injuries, all crash types. Approximate CMF +/- 1.96 SE interval includes 1.0. Near-neutral estimate is not evidence of a reliable reduction. Not longitudinal shoulder rumble strips. |
| CM029 | Provide flashing beacons at stop-controlled intersections | [446](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=446) | 0.95 | 4 | Empirical Bayes study. Adjusted SE 0.04. HSM explicitly recommends caution because uncertainty includes no effect or an increase. Aggregate scope; not an angle-only estimate. Not an RRFB pedestrian-crossing treatment. |

CM027 geometry cross-check: [FHWA SPICE User Guide, Table 19](https://cmfclearinghouse.fhwa.dot.gov/collateral/FHWA-SA-18-026%20SPICE%20Tool%20User%20Guide%20%28Final%29.pdf). CM026 signal-control mapping is an implementation inference pending original-study confirmation. The psc_name column is a historical category label; the new names do not assert FHWA Proven Safety Countermeasure designation.

Not added: CMF 11553 (separated bicycle lane) contains a negative published standard error and a non-weather-related restriction requiring clarification. It was not silently corrected or treated as bicycle-specific evidence.

## Second expansion: CM030–CM034

Five more distinct interventions added on 21 October 2026. Current total: 34 entries, comprising 32 numerical records and two processes. Official indexed detail records were checked for values, scopes, ratings and conditions. Live retrieval failed for multiple records; original-study verification remains pending. Earlier totals describe earlier snapshots.

| Entry | Treatment | Source | CMF | Stars | Evidence limitation |
|---|---|---|---:|---:|---|
| CM030 | Speed Humps | [132](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=132) | 0.6 | 3 | Meta-analysis; combined ABC injury scope excludes fatalities. Adjusted SE is 0.16; unadjusted SE is unreported. HSM reliability commentary mentions a different SE range, requiring original-source reconciliation. |
| CM031 | Dynamic Speed Feedback at Curves | [6885](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=6885) | 0.95 | 4 | Empirical Bayes estimate. Aggregate crash scope; not a run-off-road-only effect. Does not establish applicability to generic urban speed-feedback installations. |
| CM032 | Intersection Conflict Warning Systems | [8474](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=8474) | 0.704 | 5 | Empirical Bayes study of 16 sites in MN, MO and NC. Aggregate crash scope; not an angle-only CMF. Geometry, control and equipment prerequisites need manual confirmation. |
| CM033 | Wet-Reflective Pavement Markings | [8102](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=8102) | 0.893 | 5 | Wisconsin empirical Bayes study. All crash types, KABC injuries; neither wet-road-only nor KA-only evidence. Road class and existing markings remain manual prerequisites. |
| CM034 | Larger Red Signal Heads | [2333](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=2333) | 0.58 | 5 | Empirical Bayes study in Winston-Salem, NC. Angle crashes at all severities. Blank area field is not evidence of rural applicability; confirm study setting before use. |

Ratings use the official points-to-stars conversion linked in the CSV. Blank source fields remain unspecified; they are not evidence of universal applicability. Conditions are preserved in the CSV and output for manual review. Costs and service lives remain blank. CM030 adjusted SE is recorded in limitations, not mislabeled as unadjusted SE.
