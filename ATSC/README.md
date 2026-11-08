# ATSC: AI Traffic-Safety Consultant

ECEN 403 Team 4. Ranks College Station road sites by expected fatal and serious-injury crashes,
backtests the ranking against the MPO High-Injury Network, drafts countermeasure memos, and
serves the results in a web app. Controlling documents: `docs/Team4_ATSC_ConOps_FSR_ICD_EVP_rev2-1.pdf`.

| Folder | Subsystem | Owner |
|---|---|---|
| `S1_Road_Network_Database/` | Road network, features, PostGIS database | Kabir Singh |
| `S2_Risk_Model_Backtest/` | Risk model and backtest (Python package `S2_Risk_Model_Backtest`) | Param Shelar |
| `S3_Countermeasure_Agent/` | Countermeasure agent and memos | Jose Ruiz Garcia |
| `S4_Web_App/` | FastAPI + React web app, deployment | Juan Lopez |
| `integration/` | Run artifacts, logs, demo assets, figures | Lead |
| `docs/` | Controlling documents and change requests | Lead |

Run everything from this folder. S2 runs as a package: `python -m S2_Risk_Model_Backtest.<module>`.
