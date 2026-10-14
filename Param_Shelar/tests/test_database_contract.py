from datetime import date

import pytest

from database import _json_value, relation


def test_snapshot_dates_are_iso():
    assert _json_value({"d": date(2022,12,31)}) == {"d": "2022-12-31"}


def test_database_identifiers_reject_injection():
    pytest.importorskip("psycopg")
    for name in ("site;DROP TABLE site", "tasc.site;drop", "site", "tasc.site.extra"):
        with pytest.raises(ValueError):
            relation(name)
