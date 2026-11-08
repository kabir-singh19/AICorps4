"""Street-name keys, so a CRIS crash "Street Name" can be compared with a road's name.

CRIS and the TxDOT roadway inventory spell the same street differently:
    crash  W ROCK PRAIRIE RD       TxDOT  ROCK PRAIRE RD           (TxDOT typo)
    crash  WILLIAM D FITCH PKWY    TxDOT  WILLIAM D. FITCH PKWY
    crash  BARRON RD               TxDOT  BARRON                    (no suffix)
    crash  S HOLLEMAN DR           TxDOT  HOLLEMAN W DR             (direction before the suffix)
    crash  EARL RUDDER FWY         TxDOT  SH0006                    (state route: code, no name)
street_key() turns any spelling into one key; base_key() also drops the suffix (RD, ST, ...).
Two names match when their keys are equal or their base keys are equal. That is loose on
purpose: map-matching still requires the crash to be near the road, so the name only has to
say which nearby road, not find it alone.
Load into the database after any change:  python ingest.py street-keys
"""
import re

from corridors import CORRIDORS

SUFFIX = {"ROAD": "RD", "DRIVE": "DR", "STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "BOULEVARD": "BLVD",
          "LANE": "LN", "PARKWAY": "PKWY", "HIGHWAY": "HWY", "CIRCLE": "CIR", "COURT": "CT", "PLACE": "PL",
          "TRAIL": "TRL", "FREEWAY": "FWY"}
SUFFIXES = set(SUFFIX.values()) | {"LOOP", "WAY", "PASS", "BEND", "XING", "SQ", "ROW", "RUN", "PATH"}
DIRECTIONS = {"N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST"}

# Fixed before anything else; seen in the 2019 TxDOT inventory for College Station.
TYPOS = {"ROCK PRAIRE": "ROCK PRAIRIE", "F&B": "F AND B"}

# Whole names that mean a TxDOT route code. The corridor spellings come from corridors.py.
ROUTE_NAMES = {
    "HARVEY MITCHELL PKWY": "FM2818",
    "EARL RUDDER FWY": "SH0006", "SH 6": "SH0006", "HWY 6": "SH0006",
    "GEORGE BUSH DR": "FM2347",
    "HARVEY RD": "SH0030",
    "FB RD": "F AND B RD",
    # Old name in the 2019 inventory for the in-city piece of Holleman Dr South (1.6 km): 68 crashes
    # within 20 m of it are reported on S HOLLEMAN DR and none on I&GN. The I&GN Road outside
    # the city is spelled IG AND N RD and keeps its own name.
    "N I AND G RD": "HOLLEMAN DR",
}


def _normalize(name):
    s = name.upper().strip()
    for wrong, right in TYPOS.items():
        s = s.replace(wrong, right)
    s = re.sub(r"[^A-Z0-9 ]", " ", s.replace(".", "").replace("'", ""))   # MERVIN'S -> MERVINS, not MERVIN S
    tokens = [SUFFIX.get(t, t) for t in s.split()]
    while len(tokens) > 1 and tokens[0] in DIRECTIONS:
        tokens = tokens[1:]
    while len(tokens) > 1 and tokens[-1] in DIRECTIONS:
        tokens = tokens[:-1]
    # TxDOT puts a one-letter direction before the suffix: HOLLEMAN W DR, SOUTHWEST E PKWY.
    # Spelled-out words stay (PARK WEST BLVD is a name), and so does IG AND N RD (I&GN Road).
    if (len(tokens) > 2 and tokens[-2] in {"N", "S", "E", "W"} and tokens[-1] in SUFFIXES
            and tokens[-3] != "AND"):
        tokens = tokens[:-2] + tokens[-1:]
    return " ".join(tokens)


ALIASES = {_normalize(s): c["route"] for c in CORRIDORS.values() for s in c["streets"]}
ALIASES.update({_normalize(s): route for s, route in ROUTE_NAMES.items()})


def street_key(name):
    """'W Rock Prairie Road' -> 'ROCK PRAIRIE RD'; 'Wellborn Rd' -> 'FM2154'. None for no name."""
    if name is None or not name.strip():
        return None
    s = _normalize(name)
    return ALIASES.get(s, s) or None


def base_key(key):
    """'ROCK PRAIRIE RD' -> 'ROCK PRAIRIE'. Route codes and one-word names are kept whole."""
    if key is None:
        return None
    tokens = key.split()
    return " ".join(tokens[:-1]) if len(tokens) > 1 and tokens[-1] in SUFFIXES else key
