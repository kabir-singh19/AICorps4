# Data Inventory

What was in the data folder (`~/Desktop/atsc_data/`, received 8 Nov 2026), what each item is used for,
and what is missing. Raw data stays outside git (see `.gitignore`). Sizes are on disk.

## Documents

| File | Size | Use |
|---|---|---|
| `Team4_AI_Traffic_Safety_Consultant_ConOps_FSR_ICD_EVP 2-1.pdf` | 1.6 MB | Controls requirement numbers, interfaces and pass criteria. Copy in `docs/`. |
| `403_Status_Update_Team4.pdf` | 1.5 MB | Status context. Copy in `docs/`. |
| `crash_risk_colab_v3 (1).ipynb` | 660 KB | Nov 4 multi-city model notebook. Copy with outputs in `S2_Risk_Model_Backtest/notebooks/`. |

## `crash_risk/` (Nov 4 notebook workspace, 393 MB)

| Path | Size | Contents | Used by this repo |
|---|---|---|---|
| `cris/*.csv` | 103 MB | 11 CRIS Query exports, 2016-2026, Bell, Brazos, Hays, McLennan, Nacogdoches, Smith, Walker counties and Denton, Lubbock, Round Rock cities. Columns: Crash ID, dates, severity, injury counts, lat/lon, street names, intersection flags, road class, on-system flag. No manner of collision, light, surface or pedestrian columns. | No. S1 crashes come from its own CRIS exports (in the database dump), which carry manner of collision, light, weather and surface. |
| `cache/segments_*.parquet`, `intersections_*.parquet` | | 0.2 mi segments and intersections for 11 cities built by the notebook | No (Nov 4 comparison only) |
| `cache/inventory_*.parquet`, `inventory_schema.json` | | TxDOT Roadway Inventory downloaded Oct 2026 (current vintage, layer last edited Oct 2026) | No. Current vintage, so it leaks post-2022 values into a 2022 backtest. |
| `cache/osm_nodes_*`, `osm_pois_*`, `osm_univ_*`, `osmnx/` | | Current OSM extracts (no 2022 snapshot) | No, same reason |
| `cache/crashes*_fa4f07309e.parquet` | | Notebook crash cache | No |
| `cache/tl_2024_*.zip`, `places.parquet` | | Census TIGER 2024 places and counties | No |
| `inputs/hin_mpo_digitized.geojson` | 225 KB | MPO CSAP Fig. 3.9 High-Injury Network, digitized, 522 lines (CRS84) | Yes: method A. Copied to `S1_Road_Network_Database/inputs/` and loaded as `tasc.hin_line`. |
| `inputs/hin_pdf_vectors.json` | 966 KB | Raw vectors pulled from the CSAP PDF | Provenance only (copied with the GeoJSON) |
| `outputs/` | 107 MB | Nov 4 results: `backtest_results.csv`, `hin_comparison.csv`, `hin_paired_differences.csv`, `cs_risk_ranking.csv`, LightGBM model text files, plots, `run_log.txt` | Nov 4 comparison numbers only |

## Database (S1, IF-09)

Restored from `S1_Road_Network_Database/dumps/tasc_v1_2022_2026-11-04.sql.gz` (in git).

| Source | Role | As of | Available as of |
|---|---|---|---|
| CRIS 2016-2022, College Station | history | 2022-12-31 | 2022-12-31 |
| CRIS 2023-2025, College Station | evaluation | 2025-12-31 | 2026-10-07 |
| TxDOT Roadway Inventory 2019 | predictor | 2019-12-31 | 2021-08-06 |
| Network `v1_2022` (0.1 mi segments, 3+ leg intersections) | predictor | 2022-12-31 | 2022-12-31 |
| OSM 2022-12-31 (network buffer, whole city, missing streets) | predictor | 2022-12-31 | 2022-12-31 |
| OSM latest (2026-07-27) | predictor, not used in the backtest | 2026-07-27 | 2026-07-27 |
| MPO HIN, digitized CSAP Fig. 3.9 | baseline (method A) | 2022-12-31 | 2026-11-04 |

Counts: 16,539 crashes (2016-01-02 to 2025-12-31); 7,224 `v1_2022` sites (5,590 segments, 402.1 mi;
1,634 intersections). Report: `integration/artifacts/s1_data_report.json` (`s1_report.py`).

## Missing or not delivered

- **Streetlights (IF-04):** no City streetlight layer was delivered. OSM `street_lamp` points exist
  (64 near the network as of 2022-12-31) but are too sparse for a feature, so no lighting feature is used.
- **TxDOT inventory 2020-2022:** no snapshot exists in S1. The 2019 snapshot is the latest leakage-safe vintage.
- **Pedestrian and bicycle crash flags:** not in any delivered CRIS export. S3 cannot report ped/bike counts.
- **2022 OSM for the notebook cities:** only current OSM is in `cache/`. The 2022 snapshot exists for College Station only, in S1.
- **Countermeasure unit costs and service lives:** blank in the S3 library; no audit-approved CMF, so benefits are qualitative.
