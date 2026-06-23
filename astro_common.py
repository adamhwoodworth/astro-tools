"""
Shared building blocks for the astro tools.

Fetching and caching the US Naval Observatory yearly rise/set tables, parsing
them, time/DST helpers, command-line argument parsing, and the ANSI color
palette used for table output. Imported by both darknights.py and fullmoon.py.
"""

import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# ANSI color codes for blue astro palette
RESET = "\033[0m"
BG_DARK_BLUE = "\033[48;5;17m"  # Dark navy blue
BG_LIGHT_BLUE = "\033[48;5;18m"  # Slightly lighter blue
HEADER_BG = "\033[48;5;19m"  # Header blue
HEADER_FG = "\033[97m"  # Bright white text
TEXT_FG = "\033[38;5;153m"  # Light blue text

# Configuration
CACHE_DIR = Path("cache")

# Month abbreviation to number mapping
MONTH_ABBREVS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

MONTH_NAMES = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
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
    pattern = r"^(\d{2})\s{2}(.+)$"

    for line in html_text.split("\n"):
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
            rise = data[month_start : month_start + 4].strip()
            set_time = data[month_start + 5 : month_start + 9].strip()

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
    if not time_str or time_str == "----" or not time_str.isdigit():
        return "N/A"

    if len(time_str) == 4:
        return f"{time_str[:2]}:{time_str[2:]}"

    return time_str


def time_to_minutes(time_str):
    """Convert HH:MM time string to minutes since midnight."""
    if time_str == "N/A":
        return None
    hours, mins = map(int, time_str.split(":"))
    return hours * 60 + mins


def shift_time(time_str, delta_hours):
    """
    Shift an HH:MM clock string by whole hours, wrapping at midnight.

    Applied at the display layer only. 'N/A' passes through unchanged.
    """
    if time_str == "N/A":
        return time_str
    total = time_to_minutes(time_str) + delta_hours * 60
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def dst_delta_hours(tz_name, year, month, day, baseline_offset_hours):
    """
    Hours to add to a USNO time on a given date to convert it from the fetch
    baseline offset to the date's actual local offset.

    USNO returns the whole year in a single fixed offset (baseline_offset_hours,
    the offset we requested). During the opposite-DST period the real local
    clock differs from that baseline; this returns that difference (e.g. +1 for
    a US Eastern summer date fetched against an EST baseline, 0 in winter).
    Noon is used so the result is unaffected by the ~02:00 DST transition.
    """
    dt = datetime(year, month, day, 12, tzinfo=ZoneInfo(tz_name))
    actual_offset = dt.utcoffset().total_seconds() / 3600
    return round(actual_offset - baseline_offset_hours)


def parse_latlong(arg):
    """Parse lat/long from a single argument string (e.g., '44.85, -66.98' or '44.85,-66.98')."""
    if "," not in arg:
        print("Error: lat,long must be separated by a comma", file=sys.stderr)
        sys.exit(1)

    parts = arg.split(",", 1)
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        print(f"Error: invalid lat,long: '{arg}'", file=sys.stderr)
        sys.exit(1)


def parse_args():
    """Parse and validate command line arguments."""
    # Check for optional flags
    no_color = "--no-color" in sys.argv
    if no_color:
        sys.argv.remove("--no-color")

    no_cache = "--no-cache" in sys.argv
    if no_cache:
        sys.argv.remove("--no-cache")

    args = sys.argv[1:]

    if not args:
        print(
            f"Usage: {sys.argv[0]} <lat,long> [year] [month] [--no-color] [--no-cache]",
            file=sys.stderr,
        )
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
            print(
                f"Error: month must be 3-letter abbreviation, got '{month_str}'",
                file=sys.stderr,
            )
            print(f"Valid months: {', '.join(MONTH_ABBREVS.keys())}", file=sys.stderr)
            sys.exit(1)
        month = MONTH_ABBREVS[month_str]

    if year is None:
        year = datetime.now().year

    return lat, lon, year, month, no_color, no_cache


def get_days_in_month(year, month):
    """Return the number of days in a given month/year."""
    days = {
        1: 31,
        2: 28,
        3: 31,
        4: 30,
        5: 31,
        6: 30,
        7: 31,
        8: 31,
        9: 30,
        10: 31,
        11: 30,
        12: 31,
    }
    if month == 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        days[2] = 29
    return days[month]
