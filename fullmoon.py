#!/usr/bin/env python3
"""
Find prime moon-near-the-horizon photo windows from US Naval Observatory data:
moonrises that occur within 61 minutes of sunset, and moonsets within 61
minutes of sunrise. Each event is rated by how tightly the moon event brackets
its paired sun event, so the best "big moon at golden hour" nights stand out.

Reuses darknights.py's fetch/parse/timezone helpers, so the cache directory,
filenames, and --no-cache behavior are identical (and the two tools share any
already-downloaded sun/moon tables).
"""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from tabulate import tabulate
from timezonefinder import TimezoneFinder

from astro_common import (
    BG_DARK_BLUE,
    BG_LIGHT_BLUE,
    HEADER_BG,
    HEADER_FG,
    MONTH_NAMES,
    RESET,
    TEXT_FG,
    dst_delta_hours,
    fetch_yearly_table,
    get_days_in_month,
    parse_args,
    parse_table,
    shift_time,
    time_to_minutes,
)

# Matching windows, in minutes. A moon event counts as "near" its sun event
# within MATCH_WINDOW; within BEST_WINDOW it is one of the best of the month;
# within CLOSEST_WINDOW it is the tightest pairing of all.
MATCH_WINDOW = 61
BEST_WINDOW = 31
CLOSEST_WINDOW = 15


def rating_for_diff(diff):
    """Star rating for how close (in minutes) a moon event is to its sun event."""
    if diff <= CLOSEST_WINDOW:
        return "★★★"
    if diff <= BEST_WINDOW:
        return "★★"
    if diff <= MATCH_WINDOW:
        return "★"
    return ""


def qualifying_events_for_day(sunrise, sunset, moonrise, moonset):
    """
    Moon/sun pairings on one day that fall within MATCH_WINDOW minutes.

    Returns a chronologically ordered list of
    (event_type, moon_time, sun_time, diff_minutes) tuples: the morning
    "Moonset / Sunrise" (if any) precedes the evening "Moonrise / Sunset".
    Times are the raw USNO (fetch-baseline) clock strings; 'N/A' values are
    skipped.
    """
    events = []

    # Morning: moonset near sunrise.
    if moonset != "N/A" and sunrise != "N/A":
        diff = abs(time_to_minutes(moonset) - time_to_minutes(sunrise))
        if diff <= MATCH_WINDOW:
            events.append(("Moonset / Sunrise", moonset, sunrise, diff))

    # Evening: moonrise near sunset.
    if moonrise != "N/A" and sunset != "N/A":
        diff = abs(time_to_minutes(moonrise) - time_to_minutes(sunset))
        if diff <= MATCH_WINDOW:
            events.append(("Moonrise / Sunset", moonrise, sunset, diff))

    return events


def build_rows(year, months, sun_html, moon_html, tz_name, baseline_offset_hours):
    """
    Build display rows for every qualifying event across the requested months.

    Matching runs on the raw fetch-baseline times (the diff between a same-day
    moon/sun pair is offset-invariant); only the displayed clock times are
    DST-corrected for their date, mirroring darknights.py.
    """
    rows = []
    for month in months:
        sun_data = parse_table(sun_html, month)
        moon_data = parse_table(moon_html, month)

        for day in range(1, get_days_in_month(year, month) + 1):
            sunrise, sunset = sun_data.get(day, ("N/A", "N/A"))
            moonrise, moonset = moon_data.get(day, ("N/A", "N/A"))

            events = qualifying_events_for_day(sunrise, sunset, moonrise, moonset)
            if not events:
                continue

            # Every event on a day shares the date's DST delta, and both halves
            # of a pair are same-day events, so one delta covers the whole row.
            delta = dst_delta_hours(tz_name, year, month, day, baseline_offset_hours)

            for event_type, moon_time, sun_time, diff in events:
                rows.append(
                    [
                        f"{MONTH_NAMES[month][:3]} {day:2d}",
                        event_type,
                        shift_time(moon_time, delta),
                        shift_time(sun_time, delta),
                        str(diff),
                        rating_for_diff(diff),
                    ]
                )

    return rows


def display(rows, title, colors):
    """Render the qualifying events as a single colored table."""
    reset, bg_dark, bg_light, header_bg, header_fg, text_fg = colors

    if not rows:
        print(f"No moonrise-near-sunset or moonset-near-sunrise events within {MATCH_WINDOW} minutes were found.")
        return

    headers = ["Date", "Event", "Moon", "Sun", "Diff", "Rating"]
    table_str = tabulate(rows, headers=headers, tablefmt="simple")
    lines = table_str.split("\n")

    max_width = max(len(line) for line in lines + [title])

    print(f"{header_bg}{header_fg}{title:<{max_width}}{reset}")
    print(f"{header_bg}{header_fg}{lines[0]:<{max_width}}{reset}")
    print(f"{header_bg}{header_fg}{lines[1]:<{max_width}}{reset}")

    for i, line in enumerate(lines[2:]):
        padded_line = f"{line:<{max_width}}"
        if i % 2 == 0:
            print(f"{bg_dark}{text_fg}{padded_line}{reset}")
        else:
            print(f"{bg_light}{text_fg}{padded_line}{reset}")


def main():
    """Fetch USNO data and display moonrise/sunset and moonset/sunrise windows."""
    lat, lon, year, month, no_color, no_cache = parse_args()

    # Compute timezone from lat/long.
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if tz_name is None:
        print(f"Error: could not determine timezone for {lat}, {lon}", file=sys.stderr)
        sys.exit(1)

    # Use January 1 to get the standard (non-DST) offset for the yearly fetch.
    dt = datetime(year, 1, 1, tzinfo=ZoneInfo(tz_name))
    offset_hours = dt.utcoffset().total_seconds() / 3600
    tz_value = int(abs(offset_hours))
    tz_sign = -1 if offset_hours <= 0 else 1

    if no_color:
        colors = ("", "", "", "", "", "")
    else:
        colors = (RESET, BG_DARK_BLUE, BG_LIGHT_BLUE, HEADER_BG, HEADER_FG, TEXT_FG)

    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    print(f"Finding moon/horizon windows for {year}...")
    print(f"Location: {abs(lat):.4f}°{lat_dir}, {abs(lon):.4f}°{lon_dir}")
    print(f"Timezone: {tz_name} (UTC{offset_hours:+.0f})")
    print()

    print("Fetching sunrise/sunset table...")
    sun_html = fetch_yearly_table(0, year, lat, lon, tz_value, tz_sign, no_cache)

    print("Fetching moonrise/moonset table...")
    moon_html = fetch_yearly_table(1, year, lat, lon, tz_value, tz_sign, no_cache)

    if not sun_html or not moon_html:
        print("Failed to fetch one or more tables.")
        return

    months = [month] if month else list(range(1, 13))
    rows = build_rows(year, months, sun_html, moon_html, tz_name, offset_hours)

    print()
    month_label = f"{MONTH_NAMES[month]} " if month else ""
    title = f"Moonrise↔sunset & moonset↔sunrise windows · {month_label}{year}"
    display(rows, title, colors)


if __name__ == "__main__":
    main()
