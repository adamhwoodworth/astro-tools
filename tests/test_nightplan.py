"""Tests for nightplan.py.

Unit tests merge hand-written nights and tide events, and read nights from the
saved 2026 USNO tables in fixtures/. Integration tests run the script live.
"""

import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from darknights import Night
from nightplan import months_in_range, nights_between, plan_rows, years_to_fetch
from tides import TideEvent

FIXTURES_DIR = Path(__file__).parent / "fixtures"
NEW_YORK = ZoneInfo("America/New_York")

SAT = Night(date(2026, 9, 19), "18:41", "20:22", "Down", "Moonrise 13:02 (next day)", "04:41", "8:19", "★★★★★★★★")
SUN = Night(date(2026, 9, 20), "18:39", "20:20", "Down", "", "04:42", "8:22", "★★★★★★★★")

EVENTS = [
    TideEvent(datetime(2026, 9, 19, 9, 28, tzinfo=UTC), "High", 5.486),
    TideEvent(datetime(2026, 9, 19, 15, 42, tzinfo=UTC), "Low", 1.859),
    # 02:05 UTC on the 20th is 22:05 EDT on the 19th.
    TideEvent(datetime(2026, 9, 20, 2, 5, tzinfo=UTC), "High", 5.76),
    TideEvent(datetime(2026, 9, 20, 10, 24, tzinfo=UTC), "High", 5.425),
]


# --- plan_rows ---------------------------------------------------------------


def test_first_tide_row_of_a_day_carries_the_night():
    rows, _ = plan_rows([SAT], EVENTS[:2], NEW_YORK, "ft")
    assert rows[0] == ["Sat Sep 19", "05:28", "High", "18.0", *SAT[1:]]


def test_later_tide_rows_leave_date_and_night_blank():
    rows, _ = plan_rows([SAT], EVENTS[:2], NEW_YORK, "ft")
    assert rows[1] == ["", "11:42", "Low", "6.1", "", "", "", "", "", "", ""]


def test_tides_are_assigned_by_local_date():
    rows, _ = plan_rows([SAT, SUN], EVENTS, NEW_YORK, "ft")
    assert [row[1] for row in rows] == ["05:28", "11:42", "22:05", "06:24"]
    assert [row[0] for row in rows] == ["Sat Sep 19", "", "", "Sun Sep 20"]


def test_bands_alternate_by_day():
    _, bands = plan_rows([SAT, SUN], EVENTS, NEW_YORK, "ft")
    assert bands == [0, 0, 0, 1]


def test_day_without_tides_still_shows_its_night():
    rows, bands = plan_rows([SAT, SUN], EVENTS[:3], NEW_YORK, "ft")
    assert rows[3] == ["Sun Sep 20", "", "", "", *SUN[1:]]
    assert bands == [0, 0, 0, 1]


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


# --- integration: live APIs --------------------------------------------------


def run_nightplan(*args):
    """Run nightplan.py with given arguments."""
    return subprocess.run(
        ["uv", "run", "nightplan.py", *args, "--no-color"],
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_single_day_shows_station_tides_and_the_verified_night():
    result = run_nightplan("44.81,-66.95", "2026", "jun", "4")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert "Station: " in result.stdout
    day = next(line for line in result.stdout.split("\n") if line.startswith("Thu Jun 04"))
    # Night columns match the verified darknights fixture row for Jun 4.
    for value in ("20:09", "22:35", "Down", "Moonrise 23:42", "02:18", "1:07"):
        assert value in day
    assert " High " in result.stdout and " Low " in result.stdout


def test_range_across_new_year_shows_both_days():
    result = run_nightplan("44.81,-66.95", "2026", "dec", "31", "+2")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    dated = [line[:10] for line in result.stdout.split("\n") if line[:3] in ("Thu", "Fri")]
    assert dated == ["Thu Dec 31", "Fri Jan 01"]


def test_december_31_night_uses_next_years_moonrise():
    result = run_nightplan("44.81,-66.95", "2026", "dec", "31")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    day = next(line for line in result.stdout.split("\n") if line.startswith("Thu Dec 31"))
    assert "Moonrise 01:25 (next day)" in day and "7:42" in day
