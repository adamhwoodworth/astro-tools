#!/usr/bin/env python3
"""
Fetch yearly astronomical tables from US Naval Observatory and display
sunrise/sunset, moonrise/moonset, and astronomical twilight data.
"""

import requests
import re
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from tabulate import tabulate
from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo

# ANSI color codes for blue astro palette
RESET = "\033[0m"
BG_DARK_BLUE = "\033[48;5;17m"    # Dark navy blue
BG_LIGHT_BLUE = "\033[48;5;18m"  # Slightly lighter blue
HEADER_BG = "\033[48;5;19m"       # Header blue
HEADER_FG = "\033[97m"           # Bright white text
TEXT_FG = "\033[38;5;153m"       # Light blue text

# Configuration
CACHE_DIR = Path("cache")

# Month abbreviation to number mapping
MONTH_ABBREVS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

MONTH_NAMES = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]


def fetch_yearly_table(task, year, lat, lon, tz, tz_sign, no_cache=False):
    """
    Fetch yearly table from USNO with caching.

    Args:
        task: 0=sunrise/sunset, 1=moonrise/moonset, 4=astronomical twilight
        year: 4-digit year
        lat: Latitude
        lon: Longitude
        tz: Timezone offset (positive integer)
        tz_sign: -1 for west of Greenwich, 1 for east
        no_cache: If True, bypass cache completely

    Returns:
        Raw text response or None if request fails
    """
    url = (
        f"https://aa.usno.navy.mil/calculated/rstt/year"
        f"?year={year}&task={task}&lat={lat}&lon={lon}"
        f"&tz={tz}&tz_sign={tz_sign}"
    )

    # Create cache filename from URL parameters
    cache_key = f"year={year}&task={task}&lat={lat}&lon={lon}&tz={tz}&tz_sign={tz_sign}"
    cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
    cache_file = CACHE_DIR / f"{cache_hash}.html"

    # Check cache if not disabled
    if not no_cache and cache_file.exists():
        print("  Using cached data")
        return cache_file.read_text()

    # Fetch from USNO
    print("  Downloading from USNO...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.text

        # Save to cache if not disabled
        if not no_cache:
            CACHE_DIR.mkdir(exist_ok=True)
            cache_file.write_text(data)
            print("  Saved to cache")

        return data
    except Exception as e:
        print(f"Error fetching data (task={task}): {e}")
        return None


def parse_table(html_text, month):
    """
    Parse the yearly table and extract data for a specific month.

    Args:
        html_text: Raw HTML response
        month: Month number (1-12)

    Returns:
        Dictionary mapping day -> (rise_time, set_time) or None for missing data
    """
    results = {}

    # Find all data rows - they start with a 2-digit day number
    pattern = r'^(\d{2})\s{2}(.+)$'

    for line in html_text.split('\n'):
        line = line.strip()
        match = re.match(pattern, line)
        if not match:
            continue

        day = int(match.group(1))
        data = match.group(2)

        # Fixed-width columns: each month takes 11 chars (4 rise + 1 space + 4 set + 2 separator)
        # Exception: last month (December) has no trailing separator
        month_start = (month - 1) * 11

        if month_start + 9 <= len(data):
            rise = data[month_start:month_start + 4].strip()
            set_time = data[month_start + 5:month_start + 9].strip()

            rise = format_time(rise)
            set_time = format_time(set_time)

            results[day] = (rise, set_time)

    return results


def format_time(time_str):
    """
    Format time string from HHMM to HH:MM.

    Args:
        time_str: Time in HHMM format or special marker

    Returns:
        Formatted time string or N/A
    """
    if not time_str or time_str == '----' or not time_str.isdigit():
        return 'N/A'

    if len(time_str) == 4:
        return f"{time_str[:2]}:{time_str[2:]}"

    return time_str


def time_to_minutes(time_str):
    """Convert HH:MM time string to minutes since midnight."""
    if time_str == 'N/A':
        return None
    hours, mins = map(int, time_str.split(':'))
    return hours * 60 + mins


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

    if moon_state == 'Down':
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
        return ('Unknown', None)

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
                return ('Up', (moonset, False, 'Moonset'))
            elif ref_mins < moonrise_mins:
                # ref_time before moonrise - moon is down, rises later tonight
                return ('Down', (moonrise, False, 'Moonrise'))
            else:
                # ref_time after moonset - moon is down, rises next day
                if next_moonrise_mins is not None:
                    return ('Down', (next_day_moonrise, True, 'Moonrise'))
                return ('Down', ('N/A', False, 'Moonrise'))
        else:
            # Moonset before moonrise (moon was up from previous day)
            if ref_mins < moonset_mins:
                return ('Up', (moonset, False, 'Moonset'))
            elif ref_mins >= moonrise_mins:
                # Moon rose again, find when it sets (next day)
                if next_moonset_mins is not None:
                    return ('Up', (next_day_moonset, True, 'Moonset'))
                return ('Up', ('N/A', False, 'Moonset'))
            else:
                # Between moonset and moonrise - moon is down
                return ('Down', (moonrise, False, 'Moonrise'))

    elif moonrise_mins is not None and moonset_mins is None:
        # Moonrise but no moonset today - moon sets next day
        if moonrise_mins <= ref_mins:
            if next_moonset_mins is not None:
                return ('Up', (next_day_moonset, True, 'Moonset'))
            return ('Up', ('N/A', False, 'Moonset'))
        else:
            # Moon rises after ref_time
            return ('Down', (moonrise, False, 'Moonrise'))

    elif moonrise_mins is None and moonset_mins is not None:
        # Moonset but no moonrise today - moon was up from previous day
        if ref_mins < moonset_mins:
            return ('Up', (moonset, False, 'Moonset'))
        else:
            # Moon already set, rises next day
            if next_moonrise_mins is not None:
                return ('Down', (next_day_moonrise, True, 'Moonrise'))
            return ('Down', ('N/A', False, 'Moonrise'))

    else:
        # No moonrise or moonset - moon either up or down all day
        # Check next day to infer
        if next_moonrise_mins is not None and next_moonset_mins is not None:
            if next_moonrise_mins < next_moonset_mins:
                return ('Down', (next_day_moonrise, True, 'Moonrise'))
            else:
                return ('Up', (next_day_moonset, True, 'Moonset'))
        return ('Unknown', None)


def parse_latlong(arg):
    """Parse lat/long from a single argument string (e.g., '44.85, -66.98' or '44.85,-66.98')."""
    if ',' not in arg:
        print("Error: lat,long must be separated by a comma", file=sys.stderr)
        sys.exit(1)

    parts = arg.split(',', 1)
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        print(f"Error: invalid lat,long: '{arg}'", file=sys.stderr)
        sys.exit(1)


def parse_args():
    """Parse and validate command line arguments."""
    # Check for optional flags
    no_color = '--no-color' in sys.argv
    if no_color:
        sys.argv.remove('--no-color')

    no_cache = '--no-cache' in sys.argv
    if no_cache:
        sys.argv.remove('--no-cache')

    args = sys.argv[1:]

    if not args:
        print(f"Usage: {sys.argv[0]} <lat,long> [year] [month] [--no-color] [--no-cache]", file=sys.stderr)
        print("  lat,long:  latitude,longitude from Google Maps", file=sys.stderr)
        print("             e.g., '44.85, -66.98' or 44.85,-66.98", file=sys.stderr)
        print("  year:      4-digit year (default: current year)", file=sys.stderr)
        print("  month:     3-letter abbreviation (default: all months)", file=sys.stderr)
        print("  --no-color: disable ANSI color codes in output", file=sys.stderr)
        print("  --no-cache: bypass cache for HTTP requests", file=sys.stderr)
        sys.exit(1)

    lat, lon = parse_latlong(args[0])
    remaining = args[1:]

    year = None
    month = None

    if remaining:
        year_str = remaining[0]
        if not year_str.isdigit() or len(year_str) != 4:
            print(f"Error: year must be 4 digits, got '{year_str}'", file=sys.stderr)
            sys.exit(1)
        year = int(year_str)

    if len(remaining) >= 2:
        month_str = remaining[1].lower()
        if month_str not in MONTH_ABBREVS:
            print(f"Error: month must be 3-letter abbreviation, got '{month_str}'", file=sys.stderr)
            print(f"Valid months: {', '.join(MONTH_ABBREVS.keys())}", file=sys.stderr)
            sys.exit(1)
        month = MONTH_ABBREVS[month_str]

    if year is None:
        year = datetime.now().year

    return lat, lon, year, month, no_color, no_cache


def get_days_in_month(year, month):
    """Return the number of days in a given month/year."""
    days = {
        1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
        7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
    }
    if month == 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        days[2] = 29
    return days[month]


def display_month(year, month, sun_html, moon_html, twilight_html, colors):
    """Parse and display astronomical data for a single month."""
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
        sun = sun_data.get(day, ('N/A', 'N/A'))
        moon = moon_data.get(day, ('N/A', 'N/A'))
        twilight = twilight_data.get(day, ('N/A', 'N/A'))

        # Get next day's data
        next_day = day + 1
        if next_day > num_days:
            next_moon = next_moon_data.get(1, ('N/A', 'N/A'))
            next_twilight = next_twilight_data.get(1, ('N/A', 'N/A'))
        else:
            next_moon = moon_data.get(next_day, ('N/A', 'N/A'))
            next_twilight = twilight_data.get(next_day, ('N/A', 'N/A'))

        sunset = sun[1]
        moonrise = moon[0]
        moonset = moon[1]
        twilight_end = twilight[1]
        next_morning_twilight = next_twilight[0]

        moon_state, event_info = get_moon_state_at_time(
            twilight_end, moonrise, moonset, next_moon[0], next_moon[1]
        )

        # Build moon event column
        moon_event = ""
        if event_info:
            event_time, is_next_day, event_type = event_info
            if is_next_day:
                moon_event = f"{event_type} {event_time} (next day)"
            else:
                moon_event = f"{event_type} {event_time}"

        # Calculate dark sky length
        dark_length = calc_dark_sky_length(
            moon_state, event_info, twilight_end, next_morning_twilight
        )

        # Calculate rating (stars for each hour of dark sky)
        if dark_length == "Never Dark" or dark_length == "N/A":
            rating = ""
        else:
            hours = int(dark_length.split(':')[0])
            rating = "\u2605" * hours

        rows.append([
            f"{MONTH_NAMES[month][:3]} {day:2d}",
            sunset,
            twilight_end,
            moon_state,
            moon_event,
            next_morning_twilight,
            dark_length,
            rating
        ])

    headers = ["Date", "Sunset", "Twi End", "Moon", "Moon Event", "Twi Start", "Dark Sky", "Rating"]

    # Get column widths from tabulate
    table_str = tabulate(rows, headers=headers, tablefmt="simple")
    lines = table_str.split('\n')

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
    print(f"Location: {abs(lat):.4f}\u00b0{lat_dir}, {abs(lon):.4f}\u00b0{lon_dir}")
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
        display_month(year, m, sun_html, moon_html, twilight_html, colors)


if __name__ == "__main__":
    main()
