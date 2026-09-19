#!/usr/bin/env python3
"""
Plan nights at the coast: for each day, the high/low tides at the nearest tide
station alongside that night's sunset, astronomical twilight, moon, and dark
sky duration.

Combines tides.py (NOAA/CHS tide predictions) and darknights.py (US Naval
Observatory tables), and takes the same date arguments as tides.py. All times
are in the requested location's time zone.
"""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from astro_common import (
    color_palette,
    date_range_parser,
    fetch_tables,
    location_timezone,
    parse_date_range_args,
    print_table,
    resolve_date_range,
    standard_offset_hours,
)
from darknights import NEXT_YEAR_TABLES, NIGHT_HEADERS, NIGHT_TABLES, night_rows
from tides import TideError, add_tide_options, build_rows, header_lines, tide_events_for

HEADERS = ["Date", "Time", "Tide", "Height", *NIGHT_HEADERS]


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


def plan_rows(nights, events, tz, units):
    """
    Table rows and day bands for the combined table.

    Each day is one block: its first row carries the date, the first tide, and
    the night; the day's remaining tides follow with those cells blank. A day
    with no tides still gets a row for its night.
    """
    events_by_date = {}
    for event in events:
        events_by_date.setdefault(event.time.astimezone(tz).date(), []).append(event)

    rows = []
    bands = []
    for band, night in enumerate(nights):
        day_events = events_by_date.get(night.date, [])
        tides = [row[1:] for row in build_rows(day_events, tz, units)] or [["", "", ""]]

        rows.append([night.date.strftime("%a %b %d"), *tides[0], *night[1:]])
        rows += [["", *tide, *[""] * len(NIGHT_HEADERS)] for tide in tides[1:]]
        bands += [band % 2] * len(tides)
    return rows, bands


def parse_cli(argv):
    """Parse and validate command line arguments."""
    parser = date_range_parser("Tides and dark-sky conditions for each day at a location.")
    add_tide_options(parser)
    parser.add_argument("--no-cache", action="store_true", help="bypass cache for USNO requests")
    return parse_date_range_args(parser, argv)


def main():
    """Fetch tides and USNO tables and display them day by day."""
    args = parse_cli(sys.argv[1:])

    tz_name = location_timezone(args.lat, args.lon)
    tz = ZoneInfo(tz_name)

    try:
        first_day, last_day = resolve_date_range(args.year, args.month, args.day, datetime.now(tz).date(), args.days)
        station, miles, events = tide_events_for(
            args.lat, args.lon, first_day, last_day, tz, args.station, args.refresh
        )
    except (TideError, ValueError, requests.RequestException) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    tables_by_year = {}
    for year, tasks in years_to_fetch(first_day, last_day):
        offset_hours = standard_offset_hours(tz_name, year)
        tables = fetch_tables(tasks, year, args.lat, args.lon, offset_hours, args.no_cache)
        if tables is None:
            print("Error: failed to fetch one or more USNO tables.", file=sys.stderr)
            sys.exit(1)
        # A moon-and-twilight-only year has no sun table
        tables_by_year[year] = ([None] * (3 - len(tables)) + tables, offset_hours)

    nights = nights_between(first_day, last_day, tables_by_year, tz_name)
    rows, bands = plan_rows(nights, events, tz, args.units)

    print()
    print_table(
        header_lines(station, miles, args.lat, args.lon, args.units, tz_name),
        HEADERS,
        rows,
        color_palette(args.no_color),
        bands=bands,
        disable_numparse=True,
        colalign=("left", "left", "left", "right"),
    )


if __name__ == "__main__":
    main()
