# Draft for staff review

Example-site demonstration. Human and engineering review required.

Generation mode: api. Automated checks cover the response contract only; they do not verify narrative claims or original studies.

## Site and crash profile

This example site is an urban segment with nighttime rear-end crash patterns. Treatments with direct support for rear-end crashes and aggregate evidence for all crash types at segments have been identified for review, with area and severity scopes checked against original studies where available.

- Site id: SYN004\_NIGHT\_REAR\_END
- Site type: segment
- Crash patterns: rear\_end
- Area type: urban
- Severity scope: All
- Time of day: night

Only the supplied attributes are known. Crash counts, severity distribution and detailed roadway inventory are not supplied by this example.

Preliminary screening only. No crash reductions or benefit rankings are calculated. Direct means crash-type support only, not verified site suitability. Broader/partial evidence is listed separately for engineering review.

## Countermeasure candidates

### CM014: Replace two-way left-turn lane with raised median

**Draft summary — human review required:** Replacing a two-way left-turn lane with a raised median is directly supported for rear-end crashes at urban segments. Evidence requires verification of treatment prerequisites, existing equipment, and original study crash-type modeling before applying to this crash subtype.

**Matcher evidence:** Recorded CMF crash types explicitly cover all requested patterns.

- Location type matches: segment.
- Area setting is compatible with the recorded study setting.
- CMF-supported crash pattern matches: rear_end.

**Required review:**

- Check treatment prerequisites, geometry, traffic volumes, and existing equipment: Existing TWLTL; urban roadway; speed 30-45 mph; AADT 4883-96080.
- Complete source verification; current status: evidence_checked_indexed

**Study record — not an approved site effect:**

- CMF: 0.77; crash scope: Angle;Fixed object;Head on;Rear end;Run off road;Sideswipe;Single vehicle; severity scope: All.
- Rating: 4 stars.
- Evidence limitation: Cross-sectional estimate. Represents this median conversion, not all access-management actions or driveway consolidation. The record lists multiple crash types. Confirm the modeled outcome in the original study before applying the scalar to any one subtype.
- Record status: indexed_record_crosschecked; original-study review: not_reviewed_this_pass.
- Source: [CMF Clearinghouse record 2514](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=2514).

## Engineering review options

### CM020: Improve street lighting illuminance and uniformity

**Draft summary — human review required:** Improving street lighting illuminance and uniformity is supported for all nighttime crashes in urban segments. Aggregate evidence requires engineering review since it does not specifically address rear-end crash reduction.

**Matcher evidence:** Aggregate crash evidence requires engineering review.

- Location type matches: segment.
- Area setting is compatible with the recorded study setting.
- Nighttime condition matches; study covers all nighttime crashes.

**Required review:**

- Aggregate CMF does not establish a reduction for the requested crash subtype alone.
- Check treatment prerequisites, geometry, traffic volumes, and existing equipment: Roadway segment average illumination increases from 0-0.5 foot-candles to greater than 0.5 through 1.0 foot-candles; nighttime only.
- Complete source verification; current status: evidence_checked_indexed

**Study record — not an approved site effect:**

- CMF: 0.679; crash scope: All nighttime crashes; severity scope: All.
- Rating: 4 stars.
- Evidence limitation: Tampa, Florida. Does not apply to daytime crashes or automatically represent intersection/pedestrian-specific lighting.
- Record status: indexed_record_crosschecked; original-study review: not_reviewed_this_pass.
- Source: [CMF Clearinghouse record 11026](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=11026).

### CM021: Install high-friction surface treatment on curves

**Draft summary — human review required:** Installing high-friction surface treatment on curves provides aggregate crash reduction evidence at segment locations but does not specifically support rear-end nighttime crashes and differs in severity scope.

**Matcher evidence:** Aggregate crash evidence requires engineering review.

- Location type matches: segment.
- Study covers all crash types combined.

**Required review:**

- Area setting needs review: study=Not specified.
- Aggregate CMF does not establish a reduction for the requested crash subtype alone.
- Severity scope is unknown or differs: requested=All; study=K;A;B;C. Do not transfer this CMF to fatal/serious-injury crashes.
- Check treatment prerequisites, geometry, traffic volumes, and existing equipment: Curves without HFST; Pennsylvania study; mean AADT 8089; record supplies no speed or traffic-volume range.
- Complete source verification; current status: evidence_checked_indexed

**Study record — not an approved site effect:**

- CMF: 0.49; crash scope: All; severity scope: K;A;B;C.
- Rating: 5 stars.
- Evidence limitation: Empirical Bayes before-after, 84 sites. Represents curve HFST, not all pavement-friction management or a wet-crash-only factor.
- Record status: indexed_record_crosschecked; original-study review: not_reviewed_this_pass.
- Source: [CMF Clearinghouse record 10319](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=10319).

### CM023: Convert four-lane undivided road to two through lanes plus center turn lane

**Draft summary — human review required:** Converting a four-lane undivided road to two through lanes plus a center turn lane is supported by aggregate crash evidence at segments, but does not isolate effects for rear-end crashes and requires engineering review for site-specific geometry and operations.

**Matcher evidence:** Aggregate crash evidence requires engineering review.

- Location type matches: segment.
- Area setting is compatible with the recorded study setting.
- Study covers all crash types combined.

**Required review:**

- Aggregate CMF does not establish a reduction for the requested crash subtype alone.
- Check treatment prerequisites, geometry, traffic volumes, and existing equipment: Existing four-lane undivided two-way road; AADT 3390-22500; Rhode Island study, 2011-2019.
- Complete source verification; current status: evidence_checked_indexed

**Study record — not an approved site effect:**

- CMF: 0.71; crash scope: All; severity scope: All.
- Rating: 3 stars.
- Evidence limitation: All crash types and severities. Not a pedestrian-specific or KA-only factor. Check traffic operations and site geometry separately.
- Record status: indexed_record_crosschecked; original-study review: not_reviewed_this_pass.
- Source: [CMF Clearinghouse record 11230](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=11230).

### CM030: Install speed humps on local roads

**Draft summary — human review required:** Installing speed humps on local roads shows aggregate crash reduction for ABC injuries but has not been verified for rear-end crash reduction, severity scope alignment, or fatal crashes, requiring engineering review.

**Matcher evidence:** Aggregate crash evidence requires engineering review.

- Location type matches: segment.
- Area setting is compatible with the recorded study setting.
- Study covers all crash types combined.

**Required review:**

- Aggregate CMF does not establish a reduction for the requested crash subtype alone.
- Severity scope is unknown or differs: requested=All; study=A;B;C. Do not transfer this CMF to fatal/serious-injury crashes.
- Check treatment prerequisites, geometry, traffic volumes, and existing equipment: Two-lane local streets in urban or suburban settings; confirm existing humps and design suitability. Segment mapping is an implementation inference.
- Complete source verification; current status: evidence_checked_indexed

**Study record — not an approved site effect:**

- CMF: 0.6; crash scope: All; severity scope: A;B;C.
- Rating: 3 stars.
- Evidence limitation: Meta-analysis; combined ABC injury scope excludes fatalities. Adjusted SE is 0.16; unadjusted SE is unreported. HSM reliability commentary mentions a different SE range, requiring original-source reconciliation.
- Record status: indexed_record_crosschecked; original-study review: not_reviewed_this_pass.
- Source: [CMF Clearinghouse record 132](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=132).

### CM033: Upgrade standard markings to wet-reflective markings

**Draft summary — human review required:** Upgrading standard markings to wet-reflective markings shows aggregate crash reduction for all crash types at segment sites but has not established a specific effect for rear-end crash reduction or severity scope consistency.

**Matcher evidence:** Aggregate crash evidence requires engineering review.

- Location type matches: segment.
- Study covers all crash types combined.

**Required review:**

- Area setting needs review: study=Not specified.
- Aggregate CMF does not establish a reduction for the requested crash subtype alone.
- Severity scope is unknown or differs: requested=All; study=K;A;B;C. Do not transfer this CMF to fatal/serious-injury crashes.
- Check treatment prerequisites, geometry, traffic volumes, and existing equipment: Freeway/expressway principal arterials; AADT 3178-78335; prior standard markings. Record area type is blank; segment mapping follows the road-treatment study.
- Complete source verification; current status: evidence_checked_indexed

**Study record — not an approved site effect:**

- CMF: 0.893; crash scope: All; severity scope: K;A;B;C.
- Rating: 5 stars.
- Evidence limitation: Wisconsin empirical Bayes study. All crash types, KABC injuries; neither wet-road-only nor KA-only evidence. Road class and existing markings remain manual prerequisites.
- Record status: indexed_record_crosschecked; original-study review: not_reviewed_this_pass.
- Source: [CMF Clearinghouse record 8102](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=8102).

## Limitations

- Matching is preliminary and does not approve a treatment or establish causation.
- Recorded CMFs cannot be used for numerical benefits in this prototype.
- The program preserves supplied study scopes and does not verify live sources.
- Exact severity-label matches do not establish full site applicability.
- Model prose requires human review even when the contract checks pass.

## Next steps

- Obtain missing geometry, traffic volumes, equipment inventory and crash details.
- Review original studies and confirm each proposed treatment’s prerequisites.
- Review the draft summaries against the evidence and document staff comments.
- Keep benefit estimates unavailable until applicable evidence and inputs are verified.

## References

- CM014: Mauga and Kaseko, 2010; Modeling and Evaluating the Safety Impacts of Access Management Features in the Las Vegas Valley. [CMF record 2514](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=2514). Supplied record-check date: 2026-10-21.
- CM020: Li et al., 2021; Development of Crash Modification Factors for Roadway Illuminance: A Matched Case-Control Study. [CMF record 11026](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=11026). Supplied record-check date: 2026-10-21.
- CM021: Merrit et al., 2020; Developing Crash-Modification Factors for High-Friction Surface Treatments. [CMF record 10319](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=10319). Supplied record-check date: 2026-10-21.
- CM023: Zhou et al., 2022; Safety Effectiveness of the Road Diet Treatment in Rhode Island. [CMF record 11230](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=11230). Supplied record-check date: 2026-10-21.
- CM030: Elvik and Vaa, 2004; The Handbook of Road Safety Measures. [CMF record 132](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=132). Supplied record-check date: 2026-10-21.
- CM033: Lyon et al., 2015; Safety Evaluation of Wet Reflective Pavement Markers. [CMF record 8102](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=8102). Supplied record-check date: 2026-10-21.
