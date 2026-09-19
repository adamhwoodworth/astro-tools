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

from astro_common import (
    MONTH_NAMES,
    color_palette,
    dst_delta_hours,
    fetch_tables,
    get_days_in_month,
    location_timezone,
    parse_args,
    parse_table,
    print_table,
    shift_time,
    standard_offset_hours,
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
    if not rows:
        print(f"No moonrise-near-sunset or moonset-near-sunrise events within {MATCH_WINDOW} minutes were found.")
        return

    print_table([title], ["Date", "Event", "Moon", "Sun", "Diff", "Rating"], rows, colors)


def main():
    """Fetch USNO data and display moonrise/sunset and moonset/sunrise windows."""
    lat, lon, year, month, no_color, no_cache = parse_args()

    tz_name = location_timezone(lat, lon)
    offset_hours = standard_offset_hours(tz_name, year)

    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    print(f"Finding moon/horizon windows for {year}...")
    print(f"Location: {abs(lat):.4f}°{lat_dir}, {abs(lon):.4f}°{lon_dir}")
    print(f"Timezone: {tz_name} (UTC{offset_hours:+.0f})")
    print()

    # Sunrise/sunset and moonrise/moonset
    tables = fetch_tables((0, 1), year, lat, lon, offset_hours, no_cache)
    if tables is None:
        print("Failed to fetch one or more tables.")
        return
    sun_html, moon_html = tables

    months = [month] if month else list(range(1, 13))
    rows = build_rows(year, months, sun_html, moon_html, tz_name, offset_hours)

    print()
    month_label = f"{MONTH_NAMES[month]} " if month else ""
    title = f"Moonrise↔sunset & moonset↔sunrise windows · {month_label}{year}"
    display(rows, title, color_palette(no_color))


if __name__ == "__main__":
    main()
