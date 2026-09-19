"""Tests for nightplan.py.

Unit tests merge hand-written nights and tide events. Integration tests run
the script live.
"""

import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from darknights import Night
from nightplan import plan_rows
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
