#!/usr/bin/env python3
"""
Fetch yearly astronomical tables from US Naval Observatory and display
sunrise/sunset, moonrise/moonset, and astronomical twilight data.
"""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from astro_tools.common import (
    MONTH_NAMES,
    color_palette,
    date_range_parser,
    day_label,
    format_utc_offset,
    location_timezone,
    parse_date_range_args,
    print_table,
    resolve_date_range,
    standard_offset_hours,
)
from astro_tools.nights import NIGHT_HEADERS, fetch_night_tables, months_in_range, nights_between


def display_month(year, month, nights, colors):
    """Display a month of nights as a colored table."""
    print()
    rows = [[day_label(night.date), *night[1:]] for night in nights]
    print_table([f"{MONTH_NAMES[month]} {year}"], ["Date", *NIGHT_HEADERS], rows, colors)


def parse_cli(argv):
    """Parse and validate command line arguments."""
    parser = date_range_parser(
        "Sunrise, sunset, astronomical twilight, moon, and moonless dark sky for each night at a location.",
        no_date="the whole current year (or, with +N, N days from today)",
    )
    parser.add_argument("--no-cache", action="store_true", help="bypass cache for USNO requests")
    return parse_date_range_args(parser, argv)


def date_range(args, today):
    """First and last nights to show; with no date at all, the whole current year."""
    year = today.year if args.year is None and args.days is None else args.year
    return resolve_date_range(year, args.month, args.day, today, args.days)


def main():
    """Fetch and display astronomical data."""
    args = parse_cli(sys.argv[1:])

    tz_name = location_timezone(args.lat, args.lon)
    try:
        first_day, last_day = date_range(args, datetime.now(ZoneInfo(tz_name)).date())
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    offset_hours = standard_offset_hours(tz_name, first_day.year)

    years = str(first_day.year) if first_day.year == last_day.year else f"{first_day.year}-{last_day.year}"
    lat_dir = "N" if args.lat >= 0 else "S"
    lon_dir = "E" if args.lon >= 0 else "W"
    print(f"Fetching astronomical data for {years}...")
    print(f"Location: {abs(args.lat):.4f}°{lat_dir}, {abs(args.lon):.4f}°{lon_dir}")
    print(f"Timezone: {tz_name} ({format_utc_offset(offset_hours)})")
    print()

    tables_by_year = fetch_night_tables(first_day, last_day, args.lat, args.lon, tz_name, args.no_cache)
    nights = nights_between(first_day, last_day, tables_by_year, tz_name)

    for year, month in months_in_range(first_day, last_day):
        month_nights = [night for night in nights if (night.date.year, night.date.month) == (year, month)]
        display_month(year, month, month_nights, color_palette(args.no_color))


if __name__ == "__main__":
    main()
