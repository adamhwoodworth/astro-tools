#!/usr/bin/env python3
"""
Print a table of high/low tide predictions for the tide station nearest a
latitude/longitude. See astro_tools/tides.py for how stations and predictions
are found.
"""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from timezonefinder import TimezoneFinder

from astro_tools.common import color_palette, date_range_parser, parse_date_range_args, print_table, resolve_date_range
from astro_tools.tides import TideError, add_tide_options, build_rows, group_days, header_lines, tide_events_for


def parse_cli(argv):
    """Parse and validate command line arguments."""
    parser = date_range_parser("High/low tide table for the tide station nearest a location.")
    add_tide_options(parser)
    parser.add_argument("--tz", help="display time zone, e.g. America/St_Johns (default: the location's)")
    return parse_date_range_args(parser, argv)


def display(rows, header, colors):
    """
    Render the station header and tide rows as a single colored table, with
    the background striped by day rather than by row.
    """
    rows, bands = group_days(rows)
    print_table(
        header,
        ["Date", "Time", "Tide", "Height"],
        rows,
        colors,
        bands=bands,
        disable_numparse=True,
        colalign=("left", "left", "left", "right"),
    )


def main():
    """Find the nearest tide station and display its high/low tides."""
    args = parse_cli(sys.argv[1:])

    try:
        # Times are shown in the zone of the requested location (not the
        # station's, which can differ across a border) unless overridden; a
        # location the zone lookup cannot place falls back to this machine's zone.
        tz_name = args.tz or TimezoneFinder().timezone_at(lat=args.lat, lng=args.lon)
        if tz_name:
            tz = ZoneInfo(tz_name)
        else:
            tz = datetime.now().astimezone().tzinfo
            tz_name = str(tz)

        first_day, last_day = resolve_date_range(args.year, args.month, args.day, datetime.now(tz).date(), args.days)
        station, miles, events = tide_events_for(
            args.lat, args.lon, first_day, last_day, tz, args.station, args.refresh
        )
    except ZoneInfoNotFoundError:
        print(f"Error: unknown time zone '{args.tz}'", file=sys.stderr)
        sys.exit(1)
    except (TideError, ValueError, requests.RequestException) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print()
    header = header_lines(station, miles, args.lat, args.lon, args.units, tz_name)
    if not events:
        print("\n".join(header))
        print("No tide predictions were found for the requested dates.")
        return
    display(build_rows(events, tz, args.units), header, color_palette(args.no_color))


if __name__ == "__main__":
    main()
