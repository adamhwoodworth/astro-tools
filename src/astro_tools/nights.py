"""
Nights built from the US Naval Observatory yearly tables: sunrise, sunset,
astronomical twilight, the moon's state and next event, and the length of
moonless dark sky.
Used by darknights.py and nightplan.py.

A night's times are counted in minutes from midnight at the start of its date,
in the fixed offset the tables were fetched in, so a time after midnight is
24:00 or later. A night runs from noon to the next noon, which takes in an
evening twilight that ends after midnight.
"""

import sys
from datetime import date, timedelta
from typing import NamedTuple

from astro_tools.common import (
    dst_delta_hours,
    fetch_tables,
    get_days_in_month,
    parse_table,
    parse_table_events,
    shift_time,
    standard_offset_hours,
    time_to_minutes,
)

# USNO tables a night is built from: sunrise/sunset, moonrise/moonset, astronomical twilight
NIGHT_TABLES = (0, 1, 4)

# The following year's tables that the night of December 31 needs: moon and twilight
NEXT_YEAR_TABLES = (1, 4)

NIGHT_HEADERS = ["Sunrise", "Sunset", "Twi End", "Moon", "Moon Event", "Twi Start", "Dark Sky", "Rating"]

DAY = 24 * 60
NOON = 12 * 60

# USNO's twilight-table marker for the sun staying more than 18° below the horizon all day
CONTINUOUSLY_DARK = "===="

# The twilight columns of a night on which the sun never gets 18° below the horizon
NO_TWILIGHT = "None"


def night_clock(minutes, delta_hours, next_day_label=True):
    """
    A night's time as the local clock shows it.

    minutes counts from the night's first midnight in the fetch baseline
    offset; delta_hours is the DST correction for the date the time falls on.
    Times past midnight, including any the correction carries across it, are
    labelled "(next day)" unless next_day_label is False.
    """
    total = minutes + delta_hours * 60
    clock = f"{total % DAY // 60:02d}:{total % 60:02d}"
    return f"{clock} (next day)" if next_day_label and total >= DAY else clock


def minutes_to_duration(minutes):
    """Convert minutes to H:MM format."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}"


def events_by_date(months):
    """
    date -> (rises, sets) for each day of the given (year, month, table html)
    months, as parse_table_events reads them. A month whose html is None is
    left out, so its dates are unknown.
    """
    by_date = {}
    for year, month, html in months:
        if html is None:
            continue
        for day, events in parse_table_events(html, month).items():
            if day <= get_days_in_month(year, month):
                by_date[date(year, month, day)] = events
    return by_date


def night_times(by_date, night_date, column):
    """
    The times in one column (0 rises, 1 sets) on night_date and the date after,
    in order, as minutes from night_date's midnight. An unknown date adds none.
    """
    times = []
    for offset in (0, 1):
        events = by_date.get(night_date + timedelta(days=offset))
        if events:
            times += [offset * DAY + time_to_minutes(time) for time in events[column] if ":" in time]
    return sorted(times)


class Twilight(NamedTuple):
    end: int | None  # the evening's end; None when unknown or it never ends
    start: int | None  # the next morning's start; None when unknown or it never ends
    never_dark: bool = False  # the sun stays within 18° of the horizon all night


def night_twilight(twilight_by_date, night_date):
    """
    The night's astronomical twilight end and the next morning's start.

    Twilight ends in the evening or, near midsummer at high latitudes, after
    midnight, which USNO lists under the next date, so the end is the first
    one from noon to noon. When there is none the sun never gets 18° below
    the horizon (USNO marks such a date "////"), and the night is never dark.
    """
    today = twilight_by_date.get(night_date)
    tomorrow = twilight_by_date.get(night_date + timedelta(days=1))
    if today is None:
        return Twilight(None, None)

    ends = [minutes for minutes in night_times(twilight_by_date, night_date, 1) if NOON <= minutes < NOON + DAY]
    if not ends:
        # With tomorrow unknown, the end may still come after midnight
        if tomorrow is None or any(CONTINUOUSLY_DARK in column for events in (today, tomorrow) for column in events):
            return Twilight(None, None)
        return Twilight(None, None, never_dark=True)

    starts = [minutes for minutes in night_times(twilight_by_date, night_date, 0) if ends[0] < minutes < NOON + DAY]
    return Twilight(ends[0], starts[0] if starts else None)


def moon_events(moon_by_date, night_date):
    """The moonrises and moonsets on night_date and the date after as (minutes, event type), in order."""
    rises = [(minutes, "Moonrise") for minutes in night_times(moon_by_date, night_date, 0)]
    sets = [(minutes, "Moonset") for minutes in night_times(moon_by_date, night_date, 1)]
    return sorted(rises + sets)


def moon_at(events, minutes):
    """
    The moon's state at a time and its next event: (state, (minutes, event type) or None).

    The next event decides the state: the moon is up before a moonset and
    down before a moonrise. Past the last known event, the last event decides
    it instead, and the next event's time is None (unknown).
    """
    upcoming = [event for event in events if event[0] > minutes]
    if upcoming:
        return ("Up" if upcoming[0][1] == "Moonset" else "Down"), upcoming[0]
    if events:
        return ("Up", (None, "Moonset")) if events[-1][1] == "Moonrise" else ("Down", (None, "Moonrise"))
    return "Unknown", None


def moonless_minutes(events, moon_state, start, end):
    """Minutes from start to end with the moon down, given its state at start."""
    total = 0
    down_since = start if moon_state == "Down" else None
    for minutes, event_type in events:
        if not start < minutes < end:
            continue
        if event_type == "Moonrise" and down_since is not None:
            total += minutes - down_since
            down_since = None
        elif event_type == "Moonset" and down_since is None:
            down_since = minutes
    if down_since is not None:
        total += end - down_since
    return total


class Night(NamedTuple):
    date: date
    sunrise: str  # that morning, i.e. before the night begins
    sunset: str
    twilight_end: str
    moon_state: str
    moon_event: str
    next_twilight: str  # the following morning's astronomical twilight start
    dark_length: str
    rating: str


def build_night(night_date, sun, moon_by_date, twilight_by_date, tz_name, baseline_offset_hours):
    """
    The Night for night_date from its (sunrise, sunset) and the moon and
    twilight events by date.

    The moon is read at twilight end, or at sunset on a night that is never
    dark. Dark sky is the moonless time between twilight end and start.
    """
    sunrise, sunset = sun
    twilight = night_twilight(twilight_by_date, night_date)
    events = moon_events(moon_by_date, night_date)

    ref = time_to_minutes(sunset) if twilight.never_dark else twilight.end
    moon_state, next_event = ("Unknown", None) if ref is None else moon_at(events, ref)

    dark_minutes = None
    if twilight.never_dark:
        dark_length = "Never Dark"
    elif twilight.end is None or twilight.start is None or moon_state == "Unknown":
        dark_length = "N/A"
    else:
        dark_minutes = moonless_minutes(events, moon_state, twilight.end, twilight.start)
        dark_length = minutes_to_duration(dark_minutes) if dark_minutes else "Never Dark"

    # DST-correct only the displayed clock times, each by the delta for the date it falls on.
    deltas = [
        dst_delta_hours(tz_name, day.year, day.month, day.day, baseline_offset_hours)
        for day in (night_date, night_date + timedelta(days=1))
    ]

    def clock(minutes, next_day_label=True):
        return night_clock(minutes, deltas[minutes // DAY], next_day_label)

    if twilight.never_dark:
        twilight_end = next_twilight = NO_TWILIGHT
    else:
        twilight_end = "N/A" if twilight.end is None else clock(twilight.end)
        # The next morning's start needs no "(next day)": the column always means that morning.
        next_twilight = "N/A" if twilight.start is None else clock(twilight.start, next_day_label=False)

    moon_event = ""
    if next_event:
        minutes, event_type = next_event
        moon_event = f"{event_type} {'N/A' if minutes is None else clock(minutes)}"

    return Night(
        night_date,
        shift_time(sunrise, deltas[0]),
        shift_time(sunset, deltas[0]),
        twilight_end,
        moon_state,
        moon_event,
        next_twilight,
        dark_length,
        "★" * (dark_minutes // 60) if dark_minutes else "",
    )


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
    if month < 12:
        following_month, following_moon, following_twilight = (year, month + 1), moon_html, twilight_html
    else:
        following_month = (year + 1, 1)
        following_moon, following_twilight = next_year_tables or (None, None)

    moon_by_date = events_by_date([(year, month, moon_html), (*following_month, following_moon)])
    twilight_by_date = events_by_date([(year, month, twilight_html), (*following_month, following_twilight)])
    sun_data = parse_table(sun_html, month)

    return [
        build_night(
            date(year, month, day),
            sun_data.get(day, ("N/A", "N/A")),
            moon_by_date,
            twilight_by_date,
            tz_name,
            baseline_offset_hours,
        )
        for day in range(1, get_days_in_month(year, month) + 1)
    ]


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
