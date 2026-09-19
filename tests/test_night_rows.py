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


# --- December 31: the next day is in the following year's tables ---------------
#
# Read by hand from the USNO tables: on 2026-12-31 twilight ends at 17:43 with
# the moon already set (11:06). It next rises at 01:25 on 2027-01-01, giving
# 17:43 -> 01:25 = 7:42 of dark sky. Twilight starts at 05:19 on 2027-01-01.
# (2026-01-01, a year too early, has moonrise at 13:44.)


def december_nights(next_year_tables):
    tables = [(FIXTURES_DIR / f"usno_2026_{name}.html").read_text() for name in ("sun", "moon", "twilight")]
    return night_rows(2026, 12, *tables, "America/New_York", -5.0, next_year_tables)


def test_december_31_uses_the_following_years_tables():
    next_year = [(FIXTURES_DIR / f"usno_2027_{name}.html").read_text() for name in ("moon", "twilight")]
    assert december_nights(next_year)[30] == Night(
        date(2026, 12, 31), "15:57", "17:43", "Down", "Moonrise 01:25 (next day)", "05:19", "7:42", "★★★★★★★"
    )


def test_december_31_without_next_years_tables_is_unknown_not_last_januarys():
    assert december_nights(None)[30] == Night(
        date(2026, 12, 31), "15:57", "17:43", "Down", "Moonrise N/A", "N/A", "N/A", ""
    )


def test_december_30_needs_no_next_year_tables():
    # Moon set 10:46 on the 30th; next rise 00:16 on the 31st: 17:42 -> 00:16 = 6:34.
    night = december_nights(None)[29]
    assert (night.moon_event, night.dark_length) == ("Moonrise 00:16 (next day)", "6:34")
