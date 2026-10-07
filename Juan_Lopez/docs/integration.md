# Integration plan

Use `/api/v1` and the ICD Table 9 site properties: `site_id`, `site_type`, `road_name`, `length_mi`, `fsi_rate`, `rank`, `flagged`, `in_hin`, `memo_status`. GeoJSON uses EPSG:4326, with LineStrings for segments and Points for intersections.

1. Agree the model run/result tables with S1 and S2. S1 owns SQL migrations; S4 must read the shared database rather than another owner's files. Resolve intersection exposure and stable site identifiers before displaying rates.
2. Add authenticated viewer access and editor authorization for actions that generate memos. Keep DB credentials and LLM keys in server environment variables. Bind locally until these controls exist.
3. Replace read-route stubs with published-run queries and validate run/site/bounding-box inputs. Return the ICD error shape `{error, message}`.
4. Populate map layers and an accessible site list; implement site selection and run selection with consistent run IDs.
5. Display A/B/C capture rates, 95% confidence intervals, flagged mileage, and test F&SI count without favoring any method. Preserve the last published run if a new run fails.
6. Connect S3 memo status and grounding checks. Add editor-only generation/jobs endpoints. Failed grounding must block publication; service failure leaves map/backtest available.
7. Implement CSV/GeoJSON site downloads and PDF-only memo downloads. Add containers and TLS for the single reference host once interfaces are ready.

This scaffold establishes file structure only. It does not claim complete FSR compliance or verified performance/accessibility targets.
