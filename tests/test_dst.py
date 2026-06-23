"""Unit tests for DST-aware display-time adjustment.

USNO returns times in a single fixed UTC offset (the baseline used for the
fetch). During the opposite-DST period the displayed clock times must be
shifted by the difference between the date's real offset and that baseline.
The shift is applied at the display layer only, so the Up/Down/event/duration
logic keeps running on USNO's internally-consistent fixed-offset values.
"""

import subprocess

from astro_common import dst_delta_hours, shift_time
from darknights import format_moon_event


def run_cli(*args):
    return subprocess.run(
        ["uv", "run", "darknights.py", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def july_row(output, label):
    return next(line for line in output.splitlines() if line.strip().startswith(label))


def test_july_clock_times_are_dst_corrected():
    # 2026-07-01 at 44.81,-66.95 is EDT (UTC-4); USNO's EST-baseline sunset
    # 19:17 must display as 20:17 EDT, and twilight end 21:46 -> 22:46.
    result = run_cli("44.81,-66.95", "2026", "jul", "--no-color")
    assert result.returncode == 0, result.stderr

    row = july_row(result.stdout, "Jul  1")
    assert "20:17" in row, row
    assert "22:46" in row, row
    assert "19:17" not in row, row


def test_july_dark_sky_durations_unchanged_by_shift():
    # Durations are offset-invariant; the +1h shift must not alter them.
    result = run_cli("44.81,-66.95", "2026", "jul", "--no-color")
    assert result.returncode == 0, result.stderr

    assert "0:06" in july_row(result.stdout, "Jul  4")
    assert "Never Dark" in july_row(result.stdout, "Jul  1")


def test_shift_time_adds_hour():
    assert shift_time("19:17", 1) == "20:17"


def test_shift_time_no_shift_returns_same():
    assert shift_time("16:36", 0) == "16:36"


def test_shift_time_wraps_past_midnight():
    assert shift_time("23:30", 1) == "00:30"


def test_shift_time_wraps_before_midnight():
    assert shift_time("00:30", -1) == "23:30"


def test_shift_time_passes_through_na():
    assert shift_time("N/A", 1) == "N/A"


def test_dst_delta_is_plus_one_during_dst():
    # America/New_York baseline is EST (UTC-5); July is EDT (UTC-4) -> +1h.
    assert dst_delta_hours("America/New_York", 2026, 7, 15, -5) == 1


def test_dst_delta_is_zero_during_standard_time():
    # January is itself standard time, matching the baseline -> no shift.
    assert dst_delta_hours("America/New_York", 2026, 1, 15, -5) == 0


def test_moon_event_evening_shift_across_midnight_gains_next_day():
    # 23:10 same-day moonrise shifted +1h -> 00:10, now the next calendar day.
    assert format_moon_event("Moonrise", "23:10", False, 1) == "Moonrise 00:10 (next day)"


def test_moon_event_already_next_day_keeps_label_without_double_counting():
    # 06:02 next-day moonset shifted +1h -> 07:02, still just the next day.
    assert format_moon_event("Moonset", "06:02", True, 1) == "Moonset 07:02 (next day)"


def test_moon_event_same_day_evening_no_wrap_has_no_label():
    # 21:50 + 1h -> 22:50, still the same evening.
    assert format_moon_event("Moonrise", "21:50", False, 1) == "Moonrise 22:50"


def test_moon_event_no_shift_no_label():
    assert format_moon_event("Moonrise", "18:56", False, 0) == "Moonrise 18:56"


def test_moon_event_na_passes_through():
    assert format_moon_event("Moonrise", "N/A", False, 1) == "Moonrise N/A"


def test_july_late_evening_moon_events_labeled_next_day():
    result = run_cli("44.81,-66.95", "2026", "jul", "--no-color")
    assert result.returncode == 0, result.stderr
    assert "(next day)" in july_row(result.stdout, "Jul  8")  # Moonrise 00:10
    assert "(next day)" in july_row(result.stdout, "Jul 24")  # Moonset 00:58
