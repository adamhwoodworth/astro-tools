"""Unit tests for darknights.night_rows against saved USNO tables.

The tables in fixtures/ are the 2026 sun, moon, and twilight responses for
44.81,-66.95; expectations are rows of the verified expected_table_2026_jun.txt.
"""

from datetime import date
from pathlib import Path

from darknights import Night, night_rows

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def june_nights():
    tables = [(FIXTURES_DIR / f"usno_2026_{name}.html").read_text() for name in ("sun", "moon", "twilight")]
    return night_rows(2026, 6, *tables, "America/New_York", -5.0)


def test_one_night_per_day_of_the_month():
    assert [night.date for night in june_nights()] == [date(2026, 6, day) for day in range(1, 31)]


def test_night_with_a_moonrise_during_darkness():
    assert june_nights()[3] == Night(date(2026, 6, 4), "20:09", "22:35", "Down", "Moonrise 23:42", "02:18", "1:07", "★")


def test_night_that_is_never_dark():
    assert june_nights()[27] == Night(
        date(2026, 6, 28), "20:18", "22:48", "Up", "Moonset 03:52 (next day)", "02:14", "Never Dark", ""
    )
