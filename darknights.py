#!/usr/bin/env python3
"""
Fetch yearly astronomical tables from US Naval Observatory and display
sunrise/sunset, moonrise/moonset, and astronomical twilight data.
"""

from astro_tools.common import (
    MONTH_NAMES,
    color_palette,
    format_utc_offset,
    location_timezone,
    parse_args,
    print_table,
    resolve_date_range,
    standard_offset_hours,
)
from astro_tools.nights import NIGHT_HEADERS, fetch_night_tables, nights_between


def display_month(year, month, nights, colors):
    """Display a month of nights as a colored table."""
    print()
    rows = [[f"{MONTH_NAMES[month][:3]} {night.date.day:2d}", *night[1:]] for night in nights]
    print_table([f"{MONTH_NAMES[month]} {year}"], ["Date", *NIGHT_HEADERS], rows, colors)


def main():
    """Fetch and display astronomical data."""
    lat, lon, year, month, no_color, no_cache = parse_args()

    tz_name = location_timezone(lat, lon)
    offset_hours = standard_offset_hours(tz_name, year)

    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    print(f"Fetching astronomical data for {year}...")
    print(f"Location: {abs(lat):.4f}°{lat_dir}, {abs(lon):.4f}°{lon_dir}")
    print(f"Timezone: {tz_name} ({format_utc_offset(offset_hours)})")
    print()

    first_day, last_day = resolve_date_range(year, month, None, None)
    tables_by_year = fetch_night_tables(first_day, last_day, lat, lon, tz_name, no_cache)
    nights = nights_between(first_day, last_day, tables_by_year, tz_name)

    for m in [month] if month else range(1, 13):
        display_month(year, m, [night for night in nights if night.date.month == m], color_palette(no_color))


if __name__ == "__main__":
    main()
