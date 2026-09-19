"""Unit tests for building nights in darknights.py from saved USNO tables.

The tables in fixtures/ are the 2026 sun, moon, and twilight responses for
44.81,-66.95; expectations are rows of the verified expected_table_2026_jun.txt.
"""

from datetime import date
from pathlib import Path

import pytest

from darknights import Night, fetch_night_tables, months_in_range, night_rows, nights_between, years_to_fetch

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


# --- months_in_range / nights_between ----------------------------------------


def test_months_in_range_within_one_month():
    assert months_in_range(date(2026, 6, 4), date(2026, 6, 10)) == [(2026, 6)]


def test_months_in_range_crosses_a_year_boundary():
    assert months_in_range(date(2026, 11, 30), date(2027, 1, 2)) == [(2026, 11), (2026, 12), (2027, 1)]


def test_nights_between_spans_a_month_end_and_keeps_only_the_range():
    tables = [(FIXTURES_DIR / f"usno_2026_{name}.html").read_text() for name in ("sun", "moon", "twilight")]
    nights = nights_between(date(2026, 6, 29), date(2026, 7, 2), {2026: (tables, -5.0)}, "America/New_York")
    assert [night.date for night in nights] == [
        date(2026, 6, 29),
        date(2026, 6, 30),
        date(2026, 7, 1),
        date(2026, 7, 2),
    ]
    # From the verified June fixture table.
    assert nights[0].moon_event == "Moonset 04:51 (next day)"


def test_nights_between_reads_december_31s_next_day_from_the_following_year():
    tables = [(FIXTURES_DIR / f"usno_2026_{name}.html").read_text() for name in ("sun", "moon", "twilight")]
    next_year = [None] + [(FIXTURES_DIR / f"usno_2027_{name}.html").read_text() for name in ("moon", "twilight")]
    tables_by_year = {2026: (tables, -5.0), 2027: (next_year, -5.0)}

    nights = nights_between(date(2026, 12, 31), date(2026, 12, 31), tables_by_year, "America/New_York")

    # Hand-read from the USNO tables; see test_night_rows.py.
    assert (nights[0].moon_event, nights[0].dark_length) == ("Moonrise 01:25 (next day)", "7:42")


# --- years_to_fetch ----------------------------------------------------------


def test_range_within_a_year_fetches_that_years_three_tables():
    assert years_to_fetch(date(2026, 6, 4), date(2026, 6, 10)) == [(2026, (0, 1, 4))]


def test_range_ending_december_31_also_fetches_next_years_moon_and_twilight():
    assert years_to_fetch(date(2026, 12, 30), date(2026, 12, 31)) == [(2026, (0, 1, 4)), (2027, (1, 4))]


def test_range_running_into_january_fetches_both_years_in_full():
    assert years_to_fetch(date(2026, 12, 31), date(2027, 1, 1)) == [(2026, (0, 1, 4)), (2027, (0, 1, 4))]


# --- fetch_night_tables --------------------------------------------------------


def fake_fetch(failing_year=None):
    """Stands in for astro_common.fetch_tables: table names instead of downloads."""

    def fetch(tasks, year, lat, lon, offset_hours, no_cache=False):
        if year == failing_year:
            return None
        return [f"{year}-task{task}" for task in tasks]

    return fetch


def test_fetch_night_tables_for_a_range_ending_december_31():
    tables_by_year = fetch_night_tables(
        date(2026, 12, 1), date(2026, 12, 31), 44.81, -66.95, "America/New_York", fetch=fake_fetch()
    )
    assert tables_by_year == {
        2026: (["2026-task0", "2026-task1", "2026-task4"], -5.0),
        2027: ([None, "2027-task1", "2027-task4"], -5.0),
    }


def test_fetch_night_tables_exits_when_next_years_tables_cannot_be_fetched(capsys):
    with pytest.raises(SystemExit) as exit_info:
        fetch_night_tables(
            date(2026, 12, 1),
            date(2026, 12, 31),
            44.81,
            -66.95,
            "America/New_York",
            fetch=fake_fetch(failing_year=2027),
        )
    assert exit_info.value.code == 1
    assert "2027" in capsys.readouterr().err


def test_fetch_night_tables_exits_when_the_years_own_tables_cannot_be_fetched():
    with pytest.raises(SystemExit):
        fetch_night_tables(
            date(2026, 6, 1), date(2026, 6, 30), 44.81, -66.95, "America/New_York", fetch=fake_fetch(failing_year=2026)
        )
