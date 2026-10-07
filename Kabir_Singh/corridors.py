"""The three study corridors: one list used by filter_corridors.py and by the database.

`route` is the TxDOT roadway inventory HWY code the network is built from.
`streets` is every CRIS "Street Name" spelling seen for that corridor in the 2016-2025
College Station files. CRIS mixes route codes (BS0006R) with street names (S TEXAS AVE).
Load into the database after any change:  python ingest.py corridors
"""

CORRIDORS = {
    "Texas Ave": {
        "route": "BS0006R",
        "streets": [
            "BS0006R", "BS0006", "BS0006B", "BS0006S", "BI0006", "BU0006",
            "TEXAS AVE", "S TEXAS AVE", "BUSINESS SH 6STEXAS AVE",
        ],
    },
    "University Dr": {
        "route": "FM0060",
        "streets": [
            "FM0060", "FM 60", "RM0060", "SH0060", "BS0060",
            "UNIVERSITY DR", "E UNIVERSITY DR", "N UNIVERSITY DR",
            "E UNIVERSITY SUITE 205 DR",
        ],
    },
    "Wellborn Rd": {
        "route": "FM2154",
        "streets": [
            "FM2154", "FM 2154", "FM 2154 RD", "SH2154", "2154 HWY",
            "WELLBORN RD", "N WELLBORN RD", "WELLBORN ST",
        ],
    },
}

STREET_TO_CORRIDOR = {s: name for name, c in CORRIDORS.items() for s in c["streets"]}
