"""Export a validated run for S1's future transactional IF-09 importer."""
import argparse
import json
from pathlib import Path

try:
    from .artifacts import load_bundle, validate_run_id
    from .database import result_payload
except ImportError:
    from artifacts import load_bundle, validate_run_id
    from database import result_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    validate_run_id(args.run_id)
    payload = result_payload(load_bundle(Path(args.output_root)/args.run_id))
    Path(args.output).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
