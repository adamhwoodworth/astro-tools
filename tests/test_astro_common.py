"""Unit tests for the shared astro_common library.

These pure helpers underpin both darknights.py and fullmoon.py; before the
shared library was extracted they were only exercised indirectly through the
end-to-end script runs. These tests cover their behavior directly.
"""

import pytest

from astro_common import (
    format_time,
    get_days_in_month,
    parse_latlong,
    parse_table,
    time_to_minutes,
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
