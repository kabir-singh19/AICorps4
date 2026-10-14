# Run outputs

`train.py` creates immutable directories here only when run by the owner. It stages all files,
checks model reload and exact predictions, writes a checksummed completion marker, then renames
the bundle into place. It refuses an existing run ID. Existing published results are untouched.

CSV/JSON predictions, model files, feature snapshot, explanations, bootstrap/sensitivity reports,
calibration SVG/JSON, model card, provenance manifest and BIT records are retained per run.
Real results are not included in this source package. S1 imports agreed payloads into IF-09;
S4 owns publication and live export/API delivery.
