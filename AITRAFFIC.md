# Proposal: AI Traffic-Safety Consultant for College Station

**Team 4, AI Corps.** An LLM consulting tool with an ML crash-risk model and a web app.

**One-line pitch:** Predict where the next serious crashes will happen, prove it against the consultant's High-Injury Network, and auto-write the countermeasure memos a consultant would deliver.

---

## 1. The Problem

**Real safety problem**
- Brazos County, 2017 to 2022: 20,000+ crashes, 101 fatal crashes, 524 severe-injury crashes. Crash rates are above the Texas average and have risen since 2019.
- The MPO, Brazos County, Bryan, and College Station committed to zero traffic deaths and serious injuries by 2035 (Vision Zero resolutions).
- Traffic is residents' worst-rated issue in the 2025 citizen survey (21% positive on congestion management).

**Current tool: a one-time consultant snapshot**
- Kimley-Horn produced the region's Comprehensive Safety Action Plan (study began October 2023).
- Core output, the High-Injury Network (HIN): about 11% of roads carry 71% of fatal/serious crashes and 82% of bike/ped crashes. Most cluster near campus off University Drive.
- Cost comparable: Kimley-Horn charged Universal City $200K for a similar plan.

**Weakness: it looks backward**
- The HIN was built from 2017 to 2022 crash history. The MPO's own Safe System material says the goal is to proactively identify risk instead of reacting to crash history.
- Ranking roads by past counts suffers from **regression to the mean**: a road with a few unlucky years looks dangerous, then "improves" by itself.
- Empirical Bayes (EB), the industry standard, exists specifically to correct this.

---

## 2. The Solution

A web app with three parts:

1. **Risk model:** expected fatal/serious-injury (F&SI) crashes for every segment and intersection.
2. **Countermeasure agent (LLM):** for each high-risk site, pulls its crash profile, matches FHWA Proven Safety Countermeasures and crash modification factors, estimates benefit/cost, and writes a cited project memo.
3. **Backtest page:** our model vs. the consultant's HIN on crashes that happened *after* the consultant's data ends.

---

## 3. Proof It Can Work

- **Statistics:** research shows regression-to-the-mean effects are substantial and EB corrects them; EB is recommended as the standard for hotspot identification. If the HIN is mostly raw crash history, even plain EB should beat it on future crashes.
- **ML:** a GAN-based EB method (CGAN-EB) beat the standard negative binomial EB in prediction and hotspot-identification tests. A 2026 study found XGBoost-style models explained urban arterial crash data better than Poisson/negative binomial models.
- **Data:** TxDOT CRIS is public, with crashes located by latitude/longitude and bulk CSV extracts for the last 10 years. About 104 F&SI crashes/year gives roughly 300 in a 2023 to 2025 test window.
- **Caveat:** the backtest *is* the proof. We report whatever it shows.

---

## 4. The Model

### What it predicts
For each site $i$ and year $t$: expected crash count $\mu_{i,t}$. Final output: **expected F&SI crashes per mile per year**, used for ranking.

### Inputs

| Group | Features | Why |
|---|---|---|
| Exposure | Traffic volume (AADT), segment length | Strongest predictor |
| Design | Lanes, speed limit, road class, median, signal/stop control, intersection legs, turn lanes, driveway density | Conflict frequency and impact severity |
| Pedestrian context | Sidewalks, bus stops, distance to campus, bars/restaurants, schools | Walking/biking demand proxies |
| Environment | Street lighting, land use | Night crashes on unlit arterials |
| Crash history | Past counts by type (prior years only) | Local risk not captured elsewhere |
| Network | Neighbor crash rates, road-graph position | Risk spills across adjacent sites |

**Leakage rule:** every feature must be knowable as of end of 2022, or the backtest is invalid.

### Prediction steps

**Step 1: Base prediction (gradient boosting, Poisson loss)**

$$\mu_i = L_i \cdot \exp\big(f(x_i)\big), \qquad \mathcal{L} = \sum_i \big(\mu_i - y_i \log \mu_i\big)$$

$L_i$ = segment length (offset). $f$ = sum of boosted trees.

**Step 2: Overdispersion**

$$\mathrm{Var}(y_i) = \mu_i + k\,\mu_i^2$$

**Step 3: Empirical Bayes blend (summed over history years)**

$$\hat{N}_i = w_i \sum_t \mu_{i,t} + (1-w_i)\sum_t y_{i,t}, \qquad w_i = \frac{1}{1 + k\sum_t \mu_{i,t}}$$

**Step 4: Severity**

A classifier on crash-level records estimates $p_i = P(\text{F\&SI} \mid \text{crash at } i)$. With $T$ history years:

$$\text{F\&SI}_i = \frac{\hat{N}_i}{T} \cdot p_i$$

Divide by $L_i$ for the per-mile ranking rate.

**Step 5: Rank** and flag the top 11% of network length.

### Toy example
Segment with 15 crashes in 3 years (5/yr). Model expects $\mu = 2$/yr, so $\sum \mu = 6$. With $k = 0.2$:

$$w = \frac{1}{1 + 0.2 \times 6} = 0.45, \qquad \hat{N} = 0.45(6) + 0.55(15) = 10.9 \Rightarrow 3.6/\text{yr}$$

Raw counts say 5/yr; the corrected estimate is 3.6/yr. These corrections reshuffle the top 11%.

### Explanations
SHAP values break each prediction into feature contributions (e.g. "45 mph + no lighting + 3 bus stops"). These feed the LLM agent so each memo explains *why* a site was flagged.

---

## 5. Evaluation

- **Train:** 2017 to 2022 (same window as the consultant).
- **Test:** 2023 to 2025.
- **Methods compared:** (A) consultant HIN, (B) negative binomial SPF + EB, (C) our ML-EB.
- **Metric:** capture rate at 11% of network length

$$C = \frac{\text{2023 to 2025 F\&SI crashes on flagged roads}}{\text{all 2023 to 2025 F\&SI crashes}}$$

- Bootstrap confidence intervals.
- Memo quality: blind grading by a TTI safety researcher.

---

## 6. Architecture

1. **Data pipeline:** CRIS crashes (2015 to 2025, Brazos County); TxDOT roadway inventory (lanes, speed, AADT); OpenStreetMap geometry and POIs; city streetlight GIS if available; HIN GIS layer from the MPO.
2. **Map-matching:** snap crashes to ~0.1-mile segments and intersections. Location noise is real: in one TTI sample, only 25% of officer vs. TxDOT coordinates were within 50 ft.
3. **Models:** baselines A/B plus ML-EB; GNN over the road graph as a stretch goal.
4. **LLM agent (TAMU API):** tools for crash profile lookup, countermeasure/CMF search, and benefit/cost calculation. Tools compute every number; the LLM only writes and cites.
5. **Website:** React + MapLibre/deck.gl, FastAPI, Postgres + PostGIS. Pages: risk map, site detail (history, prediction, memo), backtest results, chat.

---

## 7. Team Split and Timeline

| Workstream | Owner |
|---|---|
| Data pipeline + map-matching | TBD |
| Models + backtest | Param |
| LLM agent + countermeasure library | TBD |
| Website + deployment | TBD |

- **Weeks 1 to 3 (go/no-go):** data + all three baselines. If neither EB nor ML beats the HIN, we know early.
- **Rest of fall:** model iteration; present backtest at City Hall.
- **Spring:** agent, website, expert grading, council presentation.

---

## 8. Risks

- **Model may not beat the HIN.** Mitigation: run the backtest first; EB vs. HIN is still a defensible result.
- **SS4A may end.** It was authorized by IIJA, which expires Sept 30, 2026. Pitch as safety prioritization for the city's own capital budget, not grant writing.
- **Data quality.** Crash location noise and underreporting of minor crashes; handled via map-matching tolerance and severity weighting.

---

## 9. First Actions

1. Pull the Brazos County CRIS extract (2015 to 2025).
2. Email the MPO for the High-Injury Network GIS layer.

---

## Sources

- BCS MPO Comprehensive Safety Action Plan: http://bcsmpo.org/221/Comprehensive-Safety-Action-Plan
- MPO safety presentation, Jan 2026 (crash stats, Safe System): https://wtaw.com/wp-content/uploads/2026/02/eoc012826-mpoSafety.pdf
- KBTX on crash hotspots near campus: https://www.kbtx.com/2025/04/22/crash-hotspots-bcs-prompt-safety-initiatives-mpo-txdot/
- CSAP engagement page (Kimley-Horn): https://engagekh.com/bcssafety
- Universal City Kimley-Horn contract: https://communityimpact.com/san-antonio/government/universal-city-selects-consultant-for-safe-streets-for-all-plan/
- TxDOT crash data: https://www.txdot.gov/data-maps/crash-reports-records/crash-data-analysis-statistics.html
- CRIS Query FAQ: https://ftp.txdot.gov/pub/txdot-info/trf/crash_statistics/query-faq.pdf
- TTI crash coordinate tip card: https://cts.tti.tamu.edu/files/2022/09/CrashLocationCoordinates-TipCard.pdf
- EB and regression to the mean (Persaud et al.): https://www.sciencedirect.com/science/article/abs/pii/S0001457506001734
- Clustering-based EB for hotspot ID: https://rosap.ntl.bts.gov/view/dot/63358/dot_63358_DS1.pdf
- CGAN-EB: https://www.sciencedirect.com/science/article/pii/S2046043022000594
- GLMM + XGBoost SPFs (2026): https://www.nature.com/articles/s41598-026-56168-3
- SS4A expiry context (NACo): https://www.naco.org/news/us-department-transportation-announces-newest-round-safe-streets-and-roads-all-ss4a-grant
