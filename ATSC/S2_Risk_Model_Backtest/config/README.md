# Configuration

Use default.json with a validated frozen snapshot. Feature names are an explicit allowlist;
at least five original source features are required. Numeric missing values use historical
medians with missing indicators; categorical values have separate missing/unseen encodings.

For the M2 diagnostic on the S1 corridor network, copy corridor_diagnostic.example.json to
local.json. Its length policy was agreed with S1 on 18 Oct 2026; every output from it is labeled
as not meeting FSR 3.2.1.1.

Copy database.example.json to ignored local.json for approved S1 integration views. Replace
all placeholders, and keep DATABASE_URL in the environment. The two length fields require
team agreement. Do not change a historical date merely to make the leakage check pass.

Record hyperparameters before viewing held-out 2023-2025 results. Use a new run ID for changed
inputs/config. Exact replay reads the stored configuration and refuses source/version mismatch.
