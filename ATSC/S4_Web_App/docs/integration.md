# Integration plan

Use `/api/v1` and the ICD Table 9 site properties: `site_id`, `site_type`, `road_name`, `length_mi`, `fsi_rate`, `rank`, `flagged`, `in_hin`, `memo_status`. GeoJSON uses EPSG:4326, with LineStrings for segments and Points for intersections.

1. Agree the model run/result tables with S1 and S2. S1 owns SQL migrations; S4 must read the shared database rather than another owner's files. Resolve intersection exposure and stable site identifiers before displaying rates.
2. Agree institutional viewer access and editor authorization for actions that generate memos. The current public prototype exposes approved published results only; a separate shared project password protects AI calls. This does not replace university SSO or per-user authorization. Keep DB credentials and LLM keys in server environment variables.
3. Replace the temporary JSON adapter with shared-database published-run queries. Run/site/bounding-box validation and the ICD error shape `{error, message}` are implemented for the current adapter.
4. Validate the published site layers and accessible ranked list against real model output. Point and LineString overlays use model site IDs directly. Local OpenStreetMap section selection is separate; `map_segment_id` must explicitly link an OSM section to the model's stable site ID.
5. Display A/B/C capture rates, 95% confidence intervals, flagged mileage, and test F&SI count without favoring any method. Preserve the last published run if a new run fails.
6. Connect S3 memo status and grounding checks. Add editor-only generation/jobs endpoints. Failed grounding must block publication; service failure leaves map/backtest available.
7. CSV/GeoJSON site downloads and a Render Docker package are implemented. Deploy and verify hosted HTTPS, then implement PDF-only memo downloads and the remaining production controls.

This development scaffold does not claim complete FSR compliance or verified performance/accessibility targets.

## Hosted research prototype

See [deployment.md](deployment.md) and [ai-assistant.md](ai-assistant.md). The assistant explains published evidence using a server-side provider, with project access and draft labels. It is separate from S2's risk computation and S3's grounded memo publication. Provider responses are not approved memo records. Live TAMU credentials, actual hosting, and the shared database must be verified independently; mocked connector tests do not establish those connections.

## October 18 starter adapter

The read routes now consume a validated, local JSON contract and the browser loads runs, ranked sites, model-site results, backtests, and published memos. See [model-integration.md](model-integration.md). This temporary adapter is for early local integration; it does not replace the agreed shared-database integration or independently perform model inference or memo grounding. The model schema is still a draft to agree with S1/S2/S3; the existing integration checklist remains the target.
