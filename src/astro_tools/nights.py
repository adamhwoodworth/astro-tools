"""
Nights built from the US Naval Observatory yearly tables: sunset, astronomical
twilight, the moon's state and next event, and the length of moonless dark sky.
Used by darknights.py and nightplan.py.
"""

import sys
from datetime import date, datetime, timedelta
from typing import NamedTuple

from astro_tools.common import (
    dst_delta_hours,
    fetch_tables,
    get_days_in_month,
    parse_table,
    shift_time,
    standard_offset_hours,
    time_to_minutes,
)

# USNO tables a night is built from: sunrise/sunset, moonrise/moonset, astronomical twilight
NIGHT_TABLES = (0, 1, 4)

# The following year's tables that the night of December 31 needs: moon and twilight
NEXT_YEAR_TABLES = (1, 4)

NIGHT_HEADERS = ["Sunset", "Twi End", "Moon", "Moon Event", "Twi Start", "Dark Sky", "Rating"]


def format_moon_event(event_type, event_time, is_next_day, delta_hours):
    """
    Build the moon-event display string, DST-shifting the time and recomputing
    the "(next day)" label.

    is_next_day is computed in the fetch baseline offset. Shifting the clock by
    delta_hours can carry an event across midnight (e.g. a 23:10 same-day
    moonrise becomes 00:10), which advances its calendar day relative to the
    row date; the label must reflect the day it lands on after the shift.
    """
    if event_time == "N/A":
        return f"{event_type} N/A"

    total = time_to_minutes(event_time) + delta_hours * 60
    shifted = f"{(total % (24 * 60)) // 60:02d}:{(total % (24 * 60)) % 60:02d}"
    day_offset = (1 if is_next_day else 0) + total // (24 * 60)

    if day_offset >= 1:
        return f"{event_type} {shifted} (next day)"
    return f"{event_type} {shifted}"


def minutes_to_duration(minutes):
    """Convert minutes to H:MM format."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}"


def calc_dark_sky_length(moon_state, event_info, twilight_end, next_morning_twilight):
    """
    Calculate length of moonless dark sky.

    Args:
        moon_state: 'Up' or 'Down'
        event_info: (time, is_next_day, event_type) or None
        twilight_end: End of astronomical twilight (HH:MM)
        next_morning_twilight: Start of next morning's twilight (HH:MM)

    Returns:
        String with duration or "Never Dark"
    """
    twilight_end_mins = time_to_minutes(twilight_end)
    next_twi_mins = time_to_minutes(next_morning_twilight)

    if twilight_end_mins is None or next_twi_mins is None:
        return "N/A"

    # Next morning twilight is on the next day, so add 24 hours
    next_twi_mins_adjusted = next_twi_mins + 24 * 60

    if moon_state == "Down":
        # Dark from twilight end until moonrise or next twilight, whichever is earlier
        if event_info:
            event_time, is_next_day, event_type = event_info
            event_mins = time_to_minutes(event_time)
            if event_mins is not None:
                if is_next_day:
                    event_mins_adjusted = event_mins + 24 * 60
                else:
                    event_mins_adjusted = event_mins
                # Dark until moonrise or twilight start, whichever is earlier
                dark_end = min(event_mins_adjusted, next_twi_mins_adjusted)
                dark_length = dark_end - twilight_end_mins
                return minutes_to_duration(dark_length)
        # No moonrise event, dark until next twilight
        dark_length = next_twi_mins_adjusted - twilight_end_mins
        return minutes_to_duration(dark_length)

    else:  # Moon is Up
        # Need to wait for moonset
        if event_info:
            event_time, is_next_day, event_type = event_info
            event_mins = time_to_minutes(event_time)
            if event_mins is not None:
                if is_next_day:
                    event_mins_adjusted = event_mins + 24 * 60
                else:
                    event_mins_adjusted = event_mins

                # Check if moonset is before next morning twilight
                if event_mins_adjusted < next_twi_mins_adjusted:
                    dark_length = next_twi_mins_adjusted - event_mins_adjusted
                    return minutes_to_duration(dark_length)
                else:
                    return "Never Dark"
        return "Never Dark"


def get_moon_state_at_time(ref_time, moonrise, moonset, next_day_moonrise, next_day_moonset):
    """
    Determine if moon is up or down at a reference time.

    Returns tuple: (state, event_info) where event_info is (time, is_next_day, event_type)
    event_type is 'Moonset' if moon is Up, 'Moonrise' if moon is Down
    """
    ref_mins = time_to_minutes(ref_time)
    if ref_mins is None:
        return ("Unknown", None)

    moonrise_mins = time_to_minutes(moonrise)
    moonset_mins = time_to_minutes(moonset)
    next_moonrise_mins = time_to_minutes(next_day_moonrise)
    next_moonset_mins = time_to_minutes(next_day_moonset)

    # Determine moon state at reference time
    # Moon is Up if: moonrise occurred before ref_time AND (moonset is after ref_time OR no moonset today)
    # Moon is Down if: moonset occurred before ref_time AND (moonrise is after ref_time OR no moonrise today)

    if moonrise_mins is not None and moonset_mins is not None:
        if moonrise_mins < moonset_mins:
            # Normal day: rise then set
            if moonrise_mins <= ref_mins < moonset_mins:
                return ("Up", (moonset, False, "Moonset"))
            elif ref_mins < moonrise_mins:
                # ref_time before moonrise - moon is down, rises later tonight
                return ("Down", (moonrise, False, "Moonrise"))
            else:
                # ref_time after moonset - moon is down, rises next day
                if next_moonrise_mins is not None:
                    return ("Down", (next_day_moonrise, True, "Moonrise"))
                return ("Down", ("N/A", False, "Moonrise"))
        else:
            # Moonset before moonrise (moon was up from previous day)
            if ref_mins < moonset_mins:
                return ("Up", (moonset, False, "Moonset"))
            elif ref_mins >= moonrise_mins:
                # Moon rose again, find when it sets (next day)
                if next_moonset_mins is not None:
                    return ("Up", (next_day_moonset, True, "Moonset"))
                return ("Up", ("N/A", False, "Moonset"))
            else:
                # Between moonset and moonrise - moon is down
                return ("Down", (moonrise, False, "Moonrise"))

    elif moonrise_mins is not None and moonset_mins is None:
        # Moonrise but no moonset today - moon sets next day
        if moonrise_mins <= ref_mins:
            if next_moonset_mins is not None:
                return ("Up", (next_day_moonset, True, "Moonset"))
            return ("Up", ("N/A", False, "Moonset"))
        else:
            # Moon rises after ref_time
            return ("Down", (moonrise, False, "Moonrise"))

    elif moonrise_mins is None and moonset_mins is not None:
        # Moonset but no moonrise today - moon was up from previous day
        if ref_mins < moonset_mins:
            return ("Up", (moonset, False, "Moonset"))
        else:
            # Moon already set, rises next day
            if next_moonrise_mins is not None:
                return ("Down", (next_day_moonrise, True, "Moonrise"))
            return ("Down", ("N/A", False, "Moonrise"))

    else:
        # No moonrise or moonset - moon either up or down all day
        # Check next day to infer
        if next_moonrise_mins is not None and next_moonset_mins is not None:
            if next_moonrise_mins < next_moonset_mins:
                return ("Down", (next_day_moonrise, True, "Moonrise"))
            else:
                return ("Up", (next_day_moonset, True, "Moonset"))
        return ("Unknown", None)


class Night(NamedTuple):
    date: date
    sunset: str
    twilight_end: str
    moon_state: str
    moon_event: str
    next_twilight: str  # the following morning's astronomical twilight start
    dark_length: str
    rating: str


def night_rows(year, month, sun_html, moon_html, twilight_html, tz_name, baseline_offset_hours, next_year_tables=None):
    """One Night per day of a month, from the three USNO yearly tables.

    The last night of December runs into January 1 of the following year, so
    it needs next_year_tables: that year's (moon_html, twilight_html). Without
    them its next-day values are unknown ("N/A").

    USNO data comes back in a single fixed offset (baseline_offset_hours). All
    state/event/duration logic runs on those unshifted values, where USNO's
    day bucketing is internally consistent; only the displayed clock times are
    converted to each date's actual local (DST-aware) offset.
    """
    sun_data = parse_table(sun_html, month)
    moon_data = parse_table(moon_html, month)
    twilight_data = parse_table(twilight_html, month)

    if month < 12:
        next_moon_data = parse_table(moon_html, month + 1)
        next_twilight_data = parse_table(twilight_html, month + 1)
    elif next_year_tables:
        next_moon_data = parse_table(next_year_tables[0], 1)
        next_twilight_data = parse_table(next_year_tables[1], 1)
    else:
        next_moon_data = next_twilight_data = {}

    num_days = get_days_in_month(year, month)

    nights = []
    for day in range(1, num_days + 1):
        sun = sun_data.get(day, ("N/A", "N/A"))
        moon = moon_data.get(day, ("N/A", "N/A"))
        twilight = twilight_data.get(day, ("N/A", "N/A"))

        # Get next day's data
        next_day = day + 1
        if next_day > num_days:
            next_moon = next_moon_data.get(1, ("N/A", "N/A"))
            next_twilight = next_twilight_data.get(1, ("N/A", "N/A"))
        else:
            next_moon = moon_data.get(next_day, ("N/A", "N/A"))
            next_twilight = twilight_data.get(next_day, ("N/A", "N/A"))

        sunset = sun[1]
        moonrise = moon[0]
        moonset = moon[1]
        twilight_end = twilight[1]
        next_morning_twilight = next_twilight[0]

        moon_state, event_info = get_moon_state_at_time(twilight_end, moonrise, moonset, next_moon[0], next_moon[1])

        # Calculate dark sky length (offset-invariant; uses unshifted values)
        dark_length = calc_dark_sky_length(moon_state, event_info, twilight_end, next_morning_twilight)

        # DST-correct only the displayed clock times. Each value is shifted by
        # the delta for the date it belongs to: the row's date for sunset and
        # twilight end, the following date for the next morning's twilight and
        # any "(next day)" moon event.
        cur_delta = dst_delta_hours(tz_name, year, month, day, baseline_offset_hours)
        next_date = datetime(year, month, day) + timedelta(days=1)
        next_delta = dst_delta_hours(
            tz_name,
            next_date.year,
            next_date.month,
            next_date.day,
            baseline_offset_hours,
        )

        sunset = shift_time(sunset, cur_delta)
        twilight_end = shift_time(twilight_end, cur_delta)
        next_morning_twilight = shift_time(next_morning_twilight, next_delta)

        # Build moon event column
        moon_event = ""
        if event_info:
            event_time, is_next_day, event_type = event_info
            moon_event = format_moon_event(
                event_type,
                event_time,
                is_next_day,
                next_delta if is_next_day else cur_delta,
            )

        # Calculate rating (stars for each hour of dark sky)
        if dark_length == "Never Dark" or dark_length == "N/A":
            rating = ""
        else:
            hours = int(dark_length.split(":")[0])
            rating = "★" * hours

        nights.append(
            Night(
                date(year, month, day),
                sunset,
                twilight_end,
                moon_state,
                moon_event,
                next_morning_twilight,
                dark_length,
                rating,
            )
        )

    return nights


def months_in_range(first_day, last_day):
    """The (year, month) pairs touched by first_day..last_day, in order."""
    months = []
    year, month = first_day.year, first_day.month
    while (year, month) <= (last_day.year, last_day.month):
        months.append((year, month))
        year, month = (year, month + 1) if month < 12 else (year + 1, 1)
    return months


def years_to_fetch(first_day, last_day):
    """
    The (year, USNO tasks) to fetch for first_day..last_day.

    Every year in the range needs all three night tables. A range ending on
    December 31 also needs the following year's moon and twilight tables,
    because that night ends on January 1.
    """
    years = [(year, NIGHT_TABLES) for year in range(first_day.year, last_day.year + 1)]
    if (last_day.month, last_day.day) == (12, 31):
        years.append((last_day.year + 1, NEXT_YEAR_TABLES))
    return years


def nights_between(first_day, last_day, tables_by_year, tz_name):
    """
    Nights for first_day..last_day.

    tables_by_year maps a year to ([sun, moon, twilight], offset_hours): its
    USNO tables and the fixed offset they were fetched in. The year after a
    December 31 in the range may hold only moon and twilight (sun is None).
    """
    nights = []
    for year, month in months_in_range(first_day, last_day):
        tables, offset_hours = tables_by_year[year]
        next_year = tables_by_year.get(year + 1)
        next_year_tables = next_year[0][1:] if next_year else None
        nights += night_rows(year, month, *tables, tz_name, offset_hours, next_year_tables)
    return [night for night in nights if first_day <= night.date <= last_day]


def fetch_night_tables(first_day, last_day, lat, lon, tz_name, no_cache=False, fetch=fetch_tables):
    """
    Fetch every USNO table needed for the nights first_day..last_day.

    Returns tables_by_year for nights_between. Exits with an error if any
    table cannot be fetched.
    """
    tables_by_year = {}
    for year, tasks in years_to_fetch(first_day, last_day):
        if tasks == NEXT_YEAR_TABLES:
            print(f"Fetching {year} tables for the night of December 31...")
        offset_hours = standard_offset_hours(tz_name, year)
        tables = fetch(tasks, year, lat, lon, offset_hours, no_cache)
        if tables is None:
            print(f"Error: failed to fetch one or more USNO tables for {year}.", file=sys.stderr)
            sys.exit(1)
        # A moon-and-twilight-only year has no sun table
        tables_by_year[year] = ([None] * (3 - len(tables)) + tables, offset_hours)
    return tables_by_year
