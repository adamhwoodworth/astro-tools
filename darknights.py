#!/usr/bin/env python3
"""
Fetch yearly astronomical tables from US Naval Observatory and display
sunrise/sunset, moonrise/moonset, and astronomical twilight data.
"""

import sys
from datetime import datetime, timedelta
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


def display_month(
    year,
    month,
    sun_html,
    moon_html,
    twilight_html,
    colors,
    tz_name,
    baseline_offset_hours,
):
    """Parse and display astronomical data for a single month.

    USNO data comes back in a single fixed offset (baseline_offset_hours). All
    state/event/duration logic runs on those unshifted values, where USNO's
    day bucketing is internally consistent; only the displayed clock times are
    converted to each date's actual local (DST-aware) offset.
    """
    reset, bg_dark, bg_light, header_bg, header_fg, text_fg = colors

    sun_data = parse_table(sun_html, month)
    moon_data = parse_table(moon_html, month)
    twilight_data = parse_table(twilight_html, month)

    next_month = month + 1 if month < 12 else 1
    next_moon_data = parse_table(moon_html, next_month)
    next_twilight_data = parse_table(twilight_html, next_month)

    num_days = get_days_in_month(year, month)

    print()

    rows = []
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

        rows.append(
            [
                f"{MONTH_NAMES[month][:3]} {day:2d}",
                sunset,
                twilight_end,
                moon_state,
                moon_event,
                next_morning_twilight,
                dark_length,
                rating,
            ]
        )

    headers = [
        "Date",
        "Sunset",
        "Twi End",
        "Moon",
        "Moon Event",
        "Twi Start",
        "Dark Sky",
        "Rating",
    ]

    # Get column widths from tabulate
    table_str = tabulate(rows, headers=headers, tablefmt="simple")
    lines = table_str.split("\n")

    # Find max width for full-width coloring
    max_width = max(len(line) for line in lines)

    # Print month title and header with color
    month_title = f"{MONTH_NAMES[month]} {year}"
    print(f"{header_bg}{header_fg}{month_title:<{max_width}}{reset}")
    print(f"{header_bg}{header_fg}{lines[0]:<{max_width}}{reset}")
    print(f"{header_bg}{header_fg}{lines[1]:<{max_width}}{reset}")

    # Print data rows with alternating colors
    for i, line in enumerate(lines[2:]):
        padded_line = f"{line:<{max_width}}"
        if i % 2 == 0:
            print(f"{bg_dark}{text_fg}{padded_line}{reset}")
        else:
            print(f"{bg_light}{text_fg}{padded_line}{reset}")


def main():
    """Fetch and display astronomical data."""
    lat, lon, year, month, no_color, no_cache = parse_args()

    # Compute timezone from lat/long
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if tz_name is None:
        print(f"Error: could not determine timezone for {lat}, {lon}", file=sys.stderr)
        sys.exit(1)

    # Use January 1 to get standard (non-DST) offset
    dt = datetime(year, 1, 1, tzinfo=ZoneInfo(tz_name))
    offset_hours = dt.utcoffset().total_seconds() / 3600
    tz_value = int(abs(offset_hours))
    tz_sign = -1 if offset_hours <= 0 else 1

    # Set color codes based on --no-color flag
    if no_color:
        colors = ("", "", "", "", "", "")
    else:
        colors = (RESET, BG_DARK_BLUE, BG_LIGHT_BLUE, HEADER_BG, HEADER_FG, TEXT_FG)

    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    print(f"Fetching astronomical data for {year}...")
    print(f"Location: {abs(lat):.4f}°{lat_dir}, {abs(lon):.4f}°{lon_dir}")
    print(f"Timezone: {tz_name} (UTC{offset_hours:+.0f})")
    print()

    # Fetch all three tables
    print("Fetching sunrise/sunset table...")
    sun_html = fetch_yearly_table(0, year, lat, lon, tz_value, tz_sign, no_cache)

    print("Fetching moonrise/moonset table...")
    moon_html = fetch_yearly_table(1, year, lat, lon, tz_value, tz_sign, no_cache)

    print("Fetching astronomical twilight table...")
    twilight_html = fetch_yearly_table(4, year, lat, lon, tz_value, tz_sign, no_cache)

    if not sun_html or not moon_html or not twilight_html:
        print("Failed to fetch one or more tables.")
        return

    # Determine which months to display
    if month:
        months = [month]
    else:
        months = list(range(1, 13))

    for m in months:
        display_month(year, m, sun_html, moon_html, twilight_html, colors, tz_name, offset_hours)


if __name__ == "__main__":
    main()
