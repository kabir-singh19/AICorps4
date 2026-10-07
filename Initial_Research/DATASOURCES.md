# Data Sources: Crash-Risk Model

Companion to [SAFETY_PROPOSAL.md](SAFETY_PROPOSAL.md). Everything needed to train the model, evaluate it, and power the countermeasure agent.

**Access key:** Public = download now. Request = ask the agency (route city requests through Sam Rivera).

---

## 1. Labels (what the model predicts)

| Source | What we take | Access | Link |
|---|---|---|---|
| **TxDOT CRIS** | Every reported crash: date, KABCO severity, crash type, lat/lon | Public. Query tool plus bulk CSV extracts (previous 10 years + current year) | [CRIS Query](https://cris.dot.state.tx.us/public/Query/), [TxDOT crash data](https://www.txdot.gov/data-maps/crash-reports-records/crash-data-analysis-statistics.html) |

Pull 2015 to 2025, Brazos County. Most critical source.

---

## 2. Road Network and Design Features

| Source | What we take | Access | Link |
|---|---|---|---|
| **TxDOT Roadway Inventory** | Road linework + functional class, lanes, surface, traffic counts. Published annually. | Public | [Download](https://gis-txdot.opendata.arcgis.com/datasets/TXDOT::txdot-roadway-inventory/explore) |
| **TxDOT speed limits** | Posted speed per segment | Public | [TxDOT Open Data Portal](https://gis-txdot.opendata.arcgis.com/) |
| **OpenStreetMap (Geofabrik)** | Intersections/legs, crosswalks, signals, lanes, `lit=yes` tags | Public | [Texas extract](https://download.geofabrik.de/north-america/us/texas.html) |

---

## 3. Exposure (Traffic Volume)

| Source | What we take | Access | Link |
|---|---|---|---|
| **TxDOT Annual AADT** | Yearly volumes on state/NHS roads (Texas Ave, University Dr, SH 6) | Public | [Download](https://gis-txdot.opendata.arcgis.com/maps/TXDOT::txdot-annual-average-daily-traffic-counts-public) |
| **TxDOT 5-Year Counts** | Volumes on local/county roads (collected once every 5 years) | Public | [Download](https://gis-txdot.opendata.arcgis.com/datasets/TXDOT::txdot-5-year-statewide-aadt-traffic-counts-public/about) |
| **BCS MPO travel demand model** | Modeled volumes on every road link; fills city-street gaps | Request | [bcsmpo.org](http://bcsmpo.org/SiteMap) |
| **City Traffic Engineering counts** | Portable counter data (vehicles, bikes, pedestrians) on city streets | Request | [City blog on counters](https://blog.cstx.gov/2026/09/14/behind-the-equipment-how-college-station-gathers-traffic-data-to-make-our-streets-safer/) |

---

## 4. Context (Pedestrian Demand, Land Use, Lighting)

| Source | What we take | Access | Link |
|---|---|---|---|
| **College Station Open Data** | Sidewalks, bike infrastructure, thoroughfare plan, city limits (CC BY 4.0) | Public | [GIS hub](https://data-cstx.opendata.arcgis.com/), [data.cstx.gov](https://data.cstx.gov/) |
| **OpenStreetMap POIs** | Bars, restaurants, schools, bus stops, campus buildings | Public | Same Geofabrik extract |
| **Census LEHD LODES** | Jobs by census block (daytime activity) | Public | [lehd.ces.census.gov/data](https://lehd.ces.census.gov/data/) |
| **Census ACS** | Population density, zero-car households | Public | [data.census.gov](https://data.census.gov/) |
| **Streetlights** | Lighting per segment | Request city GIS. Fallback: OSM `lit` tags or NASA Black Marble night lights | |

---

## 5. Evaluation Only (Never Train On This)

| Source | What we take | Access | Link |
|---|---|---|---|
| **BCS MPO High-Injury Network** | Consultant's flagged roads, for the head-to-head backtest | Request GIS layer | [CSAP page](http://bcsmpo.org/221/Comprehensive-Safety-Action-Plan) |

---

## 6. Countermeasure Knowledge (LLM Agent)

| Source | What we take | Access | Link |
|---|---|---|---|
| **FHWA CMF Clearinghouse** | Crash modification factors with star ratings (record CMF ID + rating per TxDOT guidance). XML/XLS download. | Public | [cmfclearinghouse.fhwa.dot.gov](https://cmfclearinghouse.fhwa.dot.gov/) |
| **FHWA Proven Safety Countermeasures** | Vetted fixes for fatal/serious crashes | Public | [highways.dot.gov](https://highways.dot.gov/safety/proven-safety-countermeasures) |
| **Crash severity costs + service life** | $ per KABCO severity and countermeasure lifespan, for benefit/cost | Public | [FHWA synthesis](https://cmfclearinghouse.fhwa.dot.gov/resources_servlifecrashcostguide.php) |

---

## Known Gaps

- **City-street traffic volume.** TxDOT counts local roads only every 5 years. Use MPO model volumes or city counts; otherwise impute from road class.
- **Year-specific road features.** Get Roadway Inventory versions for 2017 to 2022, not just current. If older years aren't online, ask TxDOT TPP.
- **Transit stops.** TAMU reroutes buses almost every semester. Use stop locations, not route numbers.

---

## Pull Order

1. **CRIS extract** (no labels, no project)
2. **Roadway Inventory + AADT** (base network + exposure)
3. **Email the MPO** for the HIN layer and travel model volumes
4. **OSM + city hub** (context features)
5. **CMF Clearinghouse** (spring, for the agent)

---

## Owners

| Source group | Owner | Status |
|---|---|---|
| CRIS | TBD | Not started |
| Roadway Inventory + AADT | TBD | Not started |
| MPO requests | TBD | Not started |
| OSM + city hub + Census | TBD | Not started |
| Countermeasure library | TBD | Not started |
