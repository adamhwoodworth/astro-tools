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

from astro_tools.common import (
    color_palette,
    date_range_parser,
    location_timezone,
    parse_date_range_args,
    print_table,
    resolve_date_range,
)
from astro_tools.nights import NIGHT_HEADERS, fetch_night_tables, nights_between
from astro_tools.tides import TideError, add_tide_options, build_rows, header_lines, tide_events_for

HEADERS = ["Date", "Time", "Tide", "Height", *NIGHT_HEADERS]


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

    tables_by_year = fetch_night_tables(first_day, last_day, args.lat, args.lon, tz_name, args.no_cache)
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
