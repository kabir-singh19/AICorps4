"""Tests for the street-name keys. No database needed.

    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from street_names import base_key, street_key  # noqa: E402


def same_street(a, b):
    ka, kb = street_key(a), street_key(b)
    return ka == kb or base_key(ka) == base_key(kb)


class StreetKeyTests(unittest.TestCase):
    def test_spellings_seen_in_cris_and_txdot_match(self):
        pairs = [
            ("W ROCK PRAIRIE RD", "ROCK PRAIRE RD"),            # TxDOT typo, crash directional
            ("WILLIAM D FITCH PKWY", "WILLIAM D. FITCH PKWY"),  # punctuation
            ("BARRON RD", "BARRON"),                            # TxDOT name without suffix
            ("FB RD", "F&B RD"),
            ("F AND B RD", "F&B RD"),
            ("Holleman Drive", "HOLLEMAN DR"),                  # case and suffix spelled out
            ("S HOLLEMAN DR", "HOLLEMAN DR"),
        ]
        for crash, road in pairs:
            self.assertTrue(same_street(crash, road), (crash, road))

    def test_street_names_of_state_routes_become_route_codes(self):
        self.assertEqual(street_key("N WELLBORN RD"), "FM2154")       # from corridors.py
        self.assertEqual(street_key("S TEXAS AVE"), "BS0006R")
        self.assertEqual(street_key("EARL RUDDER FWY"), "SH0006")
        self.assertEqual(street_key("Harvey Mitchell Parkway"), "FM2818")
        self.assertEqual(street_key("SH0006"), "SH0006")

    def test_different_streets_stay_different(self):
        self.assertFalse(same_street("ROCK PRAIRIE RD", "GREENS PRAIRIE RD"))
        self.assertFalse(same_street("TEXAS AVE", "TEXAS ST"))       # route code vs city street
        self.assertFalse(same_street("1ST ST", "2ND ST"))

    def test_same_name_with_another_suffix_matches_on_purpose(self):
        # Known looseness: GREENS PRAIRIE RD and GREENS PRAIRIE TRL are two roads that meet.
        # Distance decides between them during map-matching.
        self.assertTrue(same_street("GREENS PRAIRIE RD", "GREENS PRAIRIE TRL"))

    def test_directions_alone_and_blanks(self):
        self.assertEqual(street_key("N"), "N")                        # a lone letter is not stripped to nothing
        self.assertIsNone(street_key(""))
        self.assertIsNone(street_key(None))
        self.assertIsNone(base_key(None))
        self.assertEqual(base_key("FM2154"), "FM2154")


if __name__ == "__main__":
    unittest.main()
