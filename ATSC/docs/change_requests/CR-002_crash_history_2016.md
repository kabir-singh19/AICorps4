# CR-002: Crash history starts in 2016

**Status:** proposed by the team leader, 8 Nov 2026. Needs sponsor and City approval (FSR change rule).

**Requirement affected:** FSR backtest split (2015–2022 history); ICD IF-01 (Brazos County CRIS, 2015–2025).

**Change:** training history is 2016–2022. The test window (2023–2025) and the 31 Dec 2022 cutoff do not change.

**Why:** CRIS Query no longer serves 2015 crash records (checked when the data was pulled for M1). The HIN itself used 2017–2022, so 2016–2022 still covers its full history.

**Effect:** one fewer history year for methods B and C. No result reported so far used 2015 data.

**Open:** if TxDOT supplies 2015 through a records request, it can be loaded with `atsc ingest --source crashes` and the run repeated. Tracked as 404 work.
