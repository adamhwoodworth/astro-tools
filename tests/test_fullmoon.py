"""Tests for fullmoon.py.

Unit tests cover the pure event-matching and rating logic. Integration tests
run the script against live USNO data and compare to a verified fixture.
"""

import shutil
import subprocess
from pathlib import Path

from fullmoon import display, qualifying_events_for_day, rating_for_diff

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CACHE_DIR = Path("cache")
LATLONG = "44.81,-66.95"


def run_fullmoon(*args):
    """Run fullmoon.py with given arguments."""
    return subprocess.run(
        ["uv", "run", "fullmoon.py", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def extract_table(output):
    """Extract the events table (header row onward), trimming trailing space.

    Trailing whitespace is stripped per line so the comparison ignores the
    full-width row padding (which depends on the title length) and asserts only
    the table content and column alignment.
    """
    lines = output.split("\n")
    start = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("Date")),
        None,
    )
    if start is None:
        return ""
    table_lines = [line.rstrip() for line in lines[start:]]
    while table_lines and not table_lines[-1]:
        table_lines.pop()
    return "\n".join(table_lines)


# --- rating_for_diff -------------------------------------------------------


def test_rating_within_15_minutes_is_three_stars():
    assert rating_for_diff(6) == "★★★"


def test_rating_15_minute_boundary_is_three_stars():
    assert rating_for_diff(15) == "★★★"


def test_rating_just_past_15_minutes_is_two_stars():
    assert rating_for_diff(16) == "★★"


def test_rating_31_minute_boundary_is_two_stars():
    # 31 minutes is the "best" cutoff from the spec.
    assert rating_for_diff(31) == "★★"


def test_rating_just_past_31_minutes_is_one_star():
    assert rating_for_diff(32) == "★"


def test_rating_61_minute_boundary_is_one_star():
    assert rating_for_diff(61) == "★"


def test_rating_beyond_match_window_is_empty():
    assert rating_for_diff(62) == ""


# --- qualifying_events_for_day ---------------------------------------------


def test_moonrise_near_sunset_qualifies():
    # Moonset (23:00) is nowhere near sunrise (06:00), so only the evening
    # moonrise-near-sunset event is returned.
    events = qualifying_events_for_day("06:00", "19:18", "19:37", "23:00")
    assert events == [("Moonrise / Sunset", "19:37", "19:18", 19)]


def test_moonset_near_sunrise_qualifies():
    # Moonrise (12:00) is nowhere near sunset (19:18), so only the morning
    # moonset-near-sunrise event is returned.
    events = qualifying_events_for_day("03:45", "19:18", "12:00", "03:51")
    assert events == [("Moonset / Sunrise", "03:51", "03:45", 6)]


def test_both_events_returned_morning_first():
    events = qualifying_events_for_day("03:45", "19:18", "19:37", "03:51")
    assert events == [
        ("Moonset / Sunrise", "03:51", "03:45", 6),
        ("Moonrise / Sunset", "19:37", "19:18", 19),
    ]


def test_no_events_when_both_outside_window():
    assert qualifying_events_for_day("06:00", "19:00", "12:00", "23:00") == []


def test_na_moon_times_are_skipped():
    assert qualifying_events_for_day("06:00", "19:00", "N/A", "N/A") == []


def test_boundary_61_minutes_is_included():
    events = qualifying_events_for_day("06:00", "19:18", "20:19", "23:00")
    assert events == [("Moonrise / Sunset", "20:19", "19:18", 61)]


def test_boundary_62_minutes_is_excluded():
    assert qualifying_events_for_day("06:00", "19:18", "20:20", "23:00") == []


# --- display ---------------------------------------------------------------


def test_display_with_no_events_prints_message(capsys):
    display([], "Title", ("", "", "", "", "", ""))
    out = capsys.readouterr().out
    assert "No moonrise-near-sunset or moonset-near-sunrise events" in out


# --- integration: output ----------------------------------------------------


def test_june_2026_matches_verified_fixture():
    result = run_fullmoon(LATLONG, "2026", "jun", "--no-color", "--no-cache")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    expected = (FIXTURES_DIR / "expected_fullmoon_2026_jun.txt").read_text().rstrip("\n")
    assert extract_table(result.stdout) == expected


# --- integration: cache behavior -------------------------------------------


def test_no_cache_downloads_two_tables_without_saving():
    """--no-cache fetches the sun and moon tables fresh and never touches cache."""
    result = run_fullmoon(LATLONG, "2026", "jun", "--no-color", "--no-cache")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert result.stdout.count("Downloading from USNO...") == 2
    assert result.stdout.count("Saved to cache") == 0
    assert result.stdout.count("Using cached data") == 0


def test_first_run_caches_then_second_run_reuses():
    """Cold run downloads and saves both tables; the next run reads both from cache."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)

    first = run_fullmoon(LATLONG, "2026", "jun", "--no-color")
    assert first.returncode == 0, f"stderr: {first.stderr}"
    assert first.stdout.count("Downloading from USNO...") == 2
    assert first.stdout.count("Saved to cache") == 2
    assert first.stdout.count("Using cached data") == 0

    second = run_fullmoon(LATLONG, "2026", "jun", "--no-color")
    assert second.returncode == 0, f"stderr: {second.stderr}"
    assert second.stdout.count("Using cached data") == 2
    assert second.stdout.count("Downloading from USNO...") == 0
    assert second.stdout.count("Saved to cache") == 0
