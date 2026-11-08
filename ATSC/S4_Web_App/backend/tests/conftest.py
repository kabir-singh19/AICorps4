"""Tests that predate the artifact adapter expect no artifact runs; point the adapter at an empty
folder unless a test sets ATSC_ARTIFACTS_DIR itself (test_artifact_api.py does)."""
import os
import tempfile

os.environ.setdefault("ATSC_ARTIFACTS_DIR", tempfile.mkdtemp(prefix="atsc-no-artifacts-"))
