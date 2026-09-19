"""Unit tests for the shared astro_tools.common library.

These pure helpers underpin both darknights.py and fullmoon.py; before the
shared library was extracted they were only exercised indirectly through the
end-to-end script runs. These tests cover their behavior directly.
"""

from datetime import date

import pytest

from astro_tools.common import (
    color_palette,
    format_time,
    format_utc_offset,
    get_days_in_month,
    parse_latlong,
    parse_table,
    print_table,
    resolve_date_range,
    standard_offset_hours,
    time_to_minutes,
    usno_tz_params,
)

# --- format_time -----------------------------------------------------------


def test_format_time_inserts_colon():
    assert format_time("0705") == "07:05"


def test_format_time_blank_marker_is_na():
    assert format_time("----") == "N/A"


def test_format_time_empty_is_na():
    assert format_time("") == "N/A"


def test_format_time_non_digit_is_na():
    assert format_time("??") == "N/A"


# --- time_to_minutes -------------------------------------------------------


def test_time_to_minutes_converts():
    assert time_to_minutes("01:30") == 90


def test_time_to_minutes_midnight_is_zero():
    assert time_to_minutes("00:00") == 0


def test_time_to_minutes_na_is_none():
    assert time_to_minutes("N/A") is None


# --- get_days_in_month -----------------------------------------------------


def test_get_days_in_month_thirty_day_month():
    assert get_days_in_month(2026, 6) == 30


def test_get_days_in_month_february_common_year():
    assert get_days_in_month(2026, 2) == 28


def test_get_days_in_month_february_leap_year():
    assert get_days_in_month(2024, 2) == 29


def test_get_days_in_month_century_is_not_leap():
    assert get_days_in_month(1900, 2) == 28


def test_get_days_in_month_400_year_is_leap():
    assert get_days_in_month(2000, 2) == 29


# --- parse_latlong ---------------------------------------------------------


def test_parse_latlong_with_space():
    assert parse_latlong("44.85, -66.98") == (44.85, -66.98)


def test_parse_latlong_without_space():
    assert parse_latlong("44.85,-66.98") == (44.85, -66.98)


def test_parse_latlong_missing_comma_exits():
    with pytest.raises(SystemExit):
        parse_latlong("44.85 -66.98")


def test_parse_latlong_non_numeric_exits():
    with pytest.raises(SystemExit):
        parse_latlong("north, west")


# --- parse_table -----------------------------------------------------------

# One synthetic data row in the USNO fixed-width layout: a 2-digit day, two
# spaces, then 11 chars per month (4 rise, 1 space, 4 set, 2 separator). Here
# the January and February columns are populated.
SAMPLE_ROW = "01  0705 1600  0650 1700"


def test_parse_table_extracts_first_month_columns():
    assert parse_table(SAMPLE_ROW, 1) == {1: ("07:05", "16:00")}


def test_parse_table_reads_second_month_columns():
    assert parse_table(SAMPLE_ROW, 2) == {1: ("06:50", "17:00")}


def test_parse_table_ignores_non_data_lines():
    assert parse_table("Sunrise and Sunset Table", 1) == {}


# --- standard_offset_hours / usno_tz_params -----------------------------------


def test_standard_offset_ignores_daylight_saving():
    assert standard_offset_hours("America/New_York", 2026) == -5.0


def test_usno_tz_params_west_of_greenwich():
    assert usno_tz_params(-5.0) == (5, -1)


def test_usno_tz_params_east_of_greenwich():
    assert usno_tz_params(2.0) == (2, 1)


def test_usno_tz_params_keep_a_half_hour_offset():
    # Newfoundland standard time is UTC-3:30; truncating it to 3 shifts every time by 30 minutes.
    assert usno_tz_params(-3.5) == (3.5, -1)


def test_usno_tz_params_keep_a_quarter_hour_offset():
    # Nepal is UTC+5:45.
    assert usno_tz_params(5.75) == (5.75, 1)


def test_standard_offset_of_a_half_hour_zone():
    assert standard_offset_hours("America/St_Johns", 2026) == -3.5


# --- format_utc_offset ---------------------------------------------------------


def test_format_whole_hour_offset():
    assert format_utc_offset(-5.0) == "UTC-5"


def test_format_half_hour_offset_west():
    assert format_utc_offset(-3.5) == "UTC-3:30"


def test_format_quarter_hour_offset_east():
    assert format_utc_offset(5.75) == "UTC+5:45"


# --- color_palette / print_table ----------------------------------------------

MARKERS = ("", "<dark>", "<light>", "<head>", "", "")
ROWS = [["a", "1"], ["b", "2"], ["c", "3"]]


def backgrounds(output):
    return [line[: line.index(">") + 1] for line in output.rstrip("\n").split("\n")]


def test_print_table_stripes_rows_alternately_by_default(capsys):
    print_table(["Title"], ["K", "V"], ROWS, MARKERS)
    assert backgrounds(capsys.readouterr().out) == ["<head>", "<head>", "<head>", "<dark>", "<light>", "<dark>"]


def test_print_table_stripes_by_band_when_given(capsys):
    print_table(["Title"], ["K", "V"], ROWS, MARKERS, bands=[0, 0, 1])
    assert backgrounds(capsys.readouterr().out)[3:] == ["<dark>", "<dark>", "<light>"]


def test_print_table_pads_every_line_to_the_widest(capsys):
    print_table(["A title much wider than the table"], ["K", "V"], ROWS, color_palette(no_color=True))
    lines = capsys.readouterr().out.rstrip("\n").split("\n")
    assert {len(line) for line in lines} == {len("A title much wider than the table")}


def test_no_color_palette_emits_no_escape_codes(capsys):
    print_table(["Title"], ["K", "V"], ROWS, color_palette(no_color=True))
    assert "\033" not in capsys.readouterr().out


def test_color_palette_emits_escape_codes(capsys):
    print_table(["Title"], ["K", "V"], ROWS, color_palette(no_color=False))
    assert "\033[" in capsys.readouterr().out


# --- resolve_date_range ------------------------------------------------------

TODAY = date(2026, 9, 19)


def test_no_date_arguments_means_today():
    assert resolve_date_range(None, None, None, TODAY) == (TODAY, TODAY)


def test_year_only_covers_the_whole_year():
    assert resolve_date_range(2027, None, None, TODAY) == (date(2027, 1, 1), date(2027, 12, 31))


def test_year_and_month_cover_the_whole_month():
    assert resolve_date_range(2028, 2, None, TODAY) == (date(2028, 2, 1), date(2028, 2, 29))


def test_year_month_day_is_a_single_day():
    assert resolve_date_range(2026, 10, 4, TODAY) == (date(2026, 10, 4), date(2026, 10, 4))


def test_day_that_does_not_exist_in_the_month_is_rejected():
    with pytest.raises(ValueError):
        resolve_date_range(2026, 2, 30, TODAY)


def test_days_counts_from_the_start_date_inclusive_across_a_month_end():
    assert resolve_date_range(2027, 8, 29, TODAY, days=7) == (date(2027, 8, 29), date(2027, 9, 4))


def test_one_day_is_the_same_as_the_single_date():
    assert resolve_date_range(2027, 8, 29, TODAY, days=1) == (date(2027, 8, 29), date(2027, 8, 29))


def test_days_without_a_date_start_today():
    assert resolve_date_range(None, None, None, TODAY, days=7) == (TODAY, date(2026, 9, 25))


def test_days_with_only_a_month_start_on_its_first_day():
    assert resolve_date_range(2027, 8, None, TODAY, days=10) == (date(2027, 8, 1), date(2027, 8, 10))
