"""Unit tests for building nights in astro_tools.nights from saved USNO tables.

The usno_2026_* and usno_2027_* tables in fixtures/ are the sun, moon, and
twilight responses for 44.81,-66.95; expectations are rows of the verified
expected_table_2026_jun.txt. The usno_2028_nl_* tables are for 49.67,-54.72,
far enough north that midsummer nights never get astronomically dark.
"""

from datetime import date
from pathlib import Path

import pytest

from astro_tools.nights import (
    Night,
    Twilight,
    fetch_night_tables,
    months_in_range,
    moon_at,
    moonless_minutes,
    night_rows,
    night_twilight,
    nights_between,
    years_to_fetch,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def june_nights():
    tables = [(FIXTURES_DIR / f"usno_2026_{name}.html").read_text() for name in ("sun", "moon", "twilight")]
    return night_rows(2026, 6, *tables, "America/New_York", -5.0)


def test_one_night_per_day_of_the_month():
    assert [night.date for night in june_nights()] == [date(2026, 6, day) for day in range(1, 31)]


def test_night_with_a_moonrise_during_darkness():
    assert june_nights()[3] == Night(
        date(2026, 6, 4), "04:44", "20:09", "22:35", "Down", "Moonrise 23:42", "02:18", "1:07", "★"
    )


def test_night_that_is_never_dark():
    assert june_nights()[27] == Night(
        date(2026, 6, 28), "04:44", "20:18", "22:48", "Up", "Moonset 03:52 (next day)", "02:14", "Never Dark", ""
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
        date(2026, 12, 31), "07:05", "15:57", "17:43", "Down", "Moonrise 01:25 (next day)", "05:19", "7:42", "★★★★★★★"
    )


def test_december_31_without_next_years_tables_is_unknown_not_last_januarys():
    assert december_nights(None)[30] == Night(
        date(2026, 12, 31), "07:05", "15:57", "17:43", "Down", "Moonrise N/A", "N/A", "N/A", ""
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
    """Stands in for astro_tools.common.fetch_tables: table names instead of downloads."""

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


# --- High latitude in summer: 2028 at 49.67,-54.72 (Newfoundland) ----------
#
# The usno_2028_nl_* fixtures are fetched in NST (UTC-3:30); summer dates
# display in NDT, an hour later. From June 3 to July 7 the sun never gets 18°
# below the horizon, which the twilight table marks "////". Around those dates
# twilight ends close to midnight: June 1's at 23:51 NST, 00:51 NDT. July 9's
# row lists two ends: 00:04 (the night of July 8, running past midnight) and
# 23:53, the second on a continuation row of its own.


def nl_nights(month):
    tables = [(FIXTURES_DIR / f"usno_2028_nl_{name}.html").read_text() for name in ("sun", "moon", "twilight")]
    return night_rows(2028, month, *tables, "America/St_Johns", -3.5)


def test_night_that_never_gets_astronomically_dark():
    # Sunset 20:14 NST; the moon is down then and rises at 21:52 NST (22:52 NDT).
    assert nl_nights(6)[7] == Night(
        date(2028, 6, 8), "05:02", "21:14", "None", "Down", "Moonrise 22:52", "None", "Never Dark", ""
    )


def test_night_whose_twilight_end_falls_past_midnight_shows_next_day():
    # Twilight ends 23:51 NST (00:51 NDT); the moon sets 01:06 NST, after twilight starts at 00:23.
    assert nl_nights(6)[0] == Night(
        date(2028, 6, 1),
        "05:06",
        "21:08",
        "00:51 (next day)",
        "Up",
        "Moonset 02:06 (next day)",
        "01:23",
        "Never Dark",
        "",
    )


def test_night_whose_twilight_ends_after_the_date_ends_is_never_dark():
    # June 2's twilight starts 00:23 but its End cell is blank, and June 3 is "////".
    night = nl_nights(6)[1]
    assert (night.twilight_end, night.next_twilight, night.dark_length) == ("None", "None", "Never Dark")


def test_moonset_shifted_past_midnight_by_dst_shows_next_day():
    # May 27: twilight ends 23:18 NST, the moon sets a minute later at 23:19 NST
    # (00:19 NDT), and twilight starts at 00:54 NST: 1:35 of dark sky.
    assert nl_nights(5)[26] == Night(
        date(2028, 5, 27),
        "05:10",
        "21:03",
        "00:18 (next day)",
        "Up",
        "Moonset 00:19 (next day)",
        "01:54",
        "1:35",
        "★",
    )


def test_twilight_end_listed_under_the_next_date_belongs_to_the_night_before():
    # July 8 is "////", but its night's twilight ends at 00:04 NST on July 9 and starts at 00:25.
    night = nl_nights(7)[7]
    assert (night.twilight_end, night.next_twilight) == ("01:04 (next day)", "01:25")


def test_second_twilight_end_on_a_continuation_row_is_that_nights():
    # July 9's own night ends at 23:53 NST (00:53 NDT) and starts at 00:36 NST on July 10.
    night = nl_nights(7)[8]
    assert (night.twilight_end, night.next_twilight) == ("00:53 (next day)", "01:36")


def test_continuation_row_does_not_erase_the_same_day_in_other_months():
    # January 8 and 9 (no DST): twilight ends 18:24 and 18:25, and starts 06:07 on the 9th and 10th.
    january = nl_nights(1)
    assert (january[7].next_twilight, january[7].dark_length) == ("06:07", "0:17")
    assert (january[8].twilight_end, january[8].moon_state) == ("18:25", "Up")


# --- night_twilight ------------------------------------------------------------

NIGHT = date(2028, 6, 1)
NEXT = date(2028, 6, 2)


def test_twilight_end_after_midnight_is_found_on_the_next_date():
    by_date = {NIGHT: (["00:30"], ["00:10"]), NEXT: (["00:40"], ["00:05"])}
    assert night_twilight(by_date, NIGHT) == Twilight(24 * 60 + 5, 24 * 60 + 40)


def test_twilight_start_before_midnight_is_found_on_the_nights_date():
    by_date = {NIGHT: (["00:05", "23:58"], ["23:40"]), NEXT: ([], ["23:45"])}
    assert night_twilight(by_date, NIGHT) == Twilight(23 * 60 + 40, 23 * 60 + 58)


def test_twilight_with_no_end_is_never_dark():
    by_date = {NIGHT: (["////"], ["////"]), NEXT: (["////"], ["////"])}
    assert night_twilight(by_date, NIGHT) == Twilight(None, None, never_dark=True)


def test_twilight_end_is_unknown_without_the_next_date():
    # The end could still come after midnight.
    assert night_twilight({NIGHT: (["00:30"], [])}, NIGHT) == Twilight(None, None)


def test_twilight_start_is_unknown_without_the_next_date():
    assert night_twilight({NIGHT: (["05:00"], ["18:00"])}, NIGHT) == Twilight(18 * 60, None)


def test_twilight_when_continuously_dark_is_unknown_not_never_dark():
    by_date = {NIGHT: (["===="], ["===="]), NEXT: (["===="], ["===="])}
    assert night_twilight(by_date, NIGHT) == Twilight(None, None)


# --- moon_at / moonless_minutes -----------------------------------------------

EVENTS = [(300, "Moonset"), (1300, "Moonrise"), (1800, "Moonset")]


def test_moon_before_a_moonset_is_up():
    assert moon_at(EVENTS, 100) == ("Up", (300, "Moonset"))


def test_moon_before_a_moonrise_is_down():
    assert moon_at(EVENTS, 1000) == ("Down", (1300, "Moonrise"))


def test_moon_past_the_last_event_takes_its_state_with_the_next_event_unknown():
    assert moon_at(EVENTS[:2], 1400) == ("Up", (None, "Moonset"))


def test_moon_without_events_is_unknown():
    assert moon_at([], 1400) == ("Unknown", None)


def test_moonless_until_moonrise():
    assert moonless_minutes(EVENTS, "Down", 1000, 1500) == 300


def test_moonless_from_moonset():
    assert moonless_minutes(EVENTS, "Up", 1500, 2000) == 200


def test_moonless_between_moonset_and_next_moonrise():
    assert moonless_minutes(EVENTS, "Up", 100, 1400) == 1000


def test_moon_up_all_night_is_no_moonless_time():
    assert moonless_minutes(EVENTS, "Up", 1350, 1700) == 0
