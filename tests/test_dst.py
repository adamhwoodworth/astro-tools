"""Unit tests for DST-aware display-time adjustment.

USNO returns times in a single fixed UTC offset (the baseline used for the
fetch). During the opposite-DST period the displayed clock times must be
shifted by the difference between the date's real offset and that baseline.
The shift is applied at the display layer only, so the Up/Down/event/duration
logic keeps running on USNO's internally-consistent fixed-offset values.
"""

import subprocess

from astro_tools.common import dst_delta_hours, shift_time
from astro_tools.nights import night_clock


def run_cli(*args):
    return subprocess.run(
        ["uv", "run", "darknights.py", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def table_row(output, label):
    """The table row for a "Mon  d" date label, skipping the weekday prefix."""
    return next(line for line in output.splitlines() if line.strip()[4:].startswith(label))


def test_july_clock_times_are_dst_corrected():
    # 2026-07-01 at 44.81,-66.95 is EDT (UTC-4); USNO's EST-baseline sunset
    # 19:17 must display as 20:17 EDT, and twilight end 21:46 -> 22:46.
    result = run_cli("44.81,-66.95", "2026", "jul", "--no-color")
    assert result.returncode == 0, result.stderr

    row = table_row(result.stdout, "Jul  1")
    assert "20:17" in row, row
    assert "22:46" in row, row
    assert "19:17" not in row, row


def test_july_dark_sky_durations_unchanged_by_shift():
    # Durations are offset-invariant; the +1h shift must not alter them.
    result = run_cli("44.81,-66.95", "2026", "jul", "--no-color")
    assert result.returncode == 0, result.stderr

    assert "0:06" in table_row(result.stdout, "Jul  4")
    assert "Never Dark" in table_row(result.stdout, "Jul  1")


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


# night_clock times count from the night's first midnight, so 24:00 and up is the next day.
NEXT_DAY = 24 * 60


def test_night_clock_evening_shift_across_midnight_gains_next_day():
    # 23:10 same-day moonrise shifted +1h -> 00:10, now the next calendar day.
    assert night_clock(23 * 60 + 10, 1) == "00:10 (next day)"


def test_night_clock_already_next_day_keeps_label_without_double_counting():
    # 06:02 next-day moonset shifted +1h -> 07:02, still just the next day.
    assert night_clock(NEXT_DAY + 6 * 60 + 2, 1) == "07:02 (next day)"


def test_night_clock_same_day_evening_no_wrap_has_no_label():
    # 21:50 + 1h -> 22:50, still the same evening.
    assert night_clock(21 * 60 + 50, 1) == "22:50"


def test_night_clock_no_shift_no_label():
    assert night_clock(18 * 60 + 56, 0) == "18:56"


def test_night_clock_can_leave_out_the_next_day_label():
    assert night_clock(NEXT_DAY + 2 * 60 + 14, 1, next_day_label=False) == "03:14"


def test_july_late_evening_moon_events_labeled_next_day():
    result = run_cli("44.81,-66.95", "2026", "jul", "--no-color")
    assert result.returncode == 0, result.stderr
    assert "(next day)" in table_row(result.stdout, "Jul  8")  # Moonrise 00:10
    assert "(next day)" in table_row(result.stdout, "Jul 24")  # Moonset 00:58


def test_half_hour_zone_times_are_not_shifted_by_30_minutes():
    # St. John's, NL keeps UTC-3:30. USNO gives sunset on 2026-01-01 as 16:20
    # for that offset (16:50 if the half hour is dropped).
    result = run_cli("47.56,-52.71", "2026", "jan", "--no-color")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Timezone: America/St_Johns (UTC-3:30)" in result.stdout
    assert table_row(result.stdout, "Jan  1").split()[4] == "16:20"


def test_december_31_uses_next_years_tables():
    # On 2026-12-31 the moon next rises at 01:25 on 2027-01-01 (7:42 of dark
    # sky); 2026-01-01's moonrise, a year too early, is 13:44.
    result = run_cli("44.81,-66.95", "2026", "dec", "--no-color")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    dec_31 = table_row(result.stdout, "Dec 31")
    assert "Moonrise 01:25 (next day)" in dec_31 and "7:42" in dec_31
