"""Make the three-corridor crash files from the CRIS Query exports.

    python filter_corridors.py ../../raw/data_*.csv --out ../../filtered

Keeps crashes whose CRIS "Street Name" is one of the spellings listed in corridors.py, adds a
"Corridor" column, and writes one file per input as <name>_3roads.csv (no preamble).

After filtering, the script lists street names that look like one of the corridors but are not
listed, so a new spelling is never dropped silently. Add it to corridors.py if it belongs.
Crashes recorded under a cross street at an intersection are not caught; that is accepted.
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter

from corridors import STREET_TO_CORRIDOR
from ingest import skip_preamble

# A street name that matches this but is not listed above gets reported for review.
LOOKS_LIKE_CORRIDOR = re.compile(r"TEXAS|UNIVERSITY|WELLBORN|0006|\b6\b|0060|\b60\b|2154")


def filter_file(path, out_dir):
    """Write the corridor crashes of one file. Returns (rows_in, rows_out, unlisted Counter)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        skip_preamble(f)
        reader = csv.DictReader(f)
        if "Street Name" not in (reader.fieldnames or []):
            sys.exit(f"{path}: no 'Street Name' column. Re-download with Street Name included.")
        rows = list(reader)
        fieldnames = reader.fieldnames + ["Corridor"]

    kept, unlisted = [], Counter()
    for row in rows:
        street = (row["Street Name"] or "").strip().upper()
        corridor = STREET_TO_CORRIDOR.get(street)
        if corridor:
            kept.append(dict(row, Corridor=corridor))
        elif LOOKS_LIKE_CORRIDOR.search(street):
            unlisted[street] += 1

    name = os.path.splitext(os.path.basename(path))[0] + "_3roads.csv"
    with open(os.path.join(out_dir, name), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(kept)
    return len(rows), len(kept), unlisted


def main(argv=None):
    parser = argparse.ArgumentParser(description="Filter CRIS crash files to the three corridors")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out", required=True, help="folder for the *_3roads.csv files")
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    all_unlisted = Counter()
    for path in sorted(args.files):
        n_in, n_out, unlisted = filter_file(path, args.out)
        all_unlisted.update(unlisted)
        print(f"{os.path.basename(path)}: {n_in} crashes, {n_out} on the corridors")

    if all_unlisted:
        print("\nStreet names that look like a corridor but are NOT in corridors.py (review these):")
        for street, n in all_unlisted.most_common():
            print(f"  {n:5d}  {street}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
