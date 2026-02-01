#!/usr/bin/env python3
"""
Fetch yearly astronomical tables from US Naval Observatory and display
sunrise/sunset, moonrise/moonset, and astronomical twilight data.
"""

import requests
import re


# Configuration
LATITUDE = 44.81
LONGITUDE = -66.95
TIMEZONE = 4  # Hours west of Greenwich (EDT = UTC-4)
YEAR = 2026
MONTH = 6  # June


def fetch_yearly_table(task):
    """
    Fetch yearly table from USNO.

    Args:
        task: 0=sunrise/sunset, 1=moonrise/moonset, 4=astronomical twilight

    Returns:
        Raw text response or None if request fails
    """
    url = (
        f"https://aa.usno.navy.mil/calculated/rstt/year"
        f"?year={YEAR}&task={task}&lat={LATITUDE}&lon={LONGITUDE}"
        f"&tz={TIMEZONE}&tz_sign=-1"
    )

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
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
    pattern = r'^(\d{2})\s+(.+)$'

    for line in html_text.split('\n'):
        line = line.strip()
        match = re.match(pattern, line)
        if not match:
            continue

        day = int(match.group(1))
        rest = match.group(2)

        # Split into month pairs - each month has rise and set times
        # Format: "HHMM HHMM" for each month, separated by spaces
        parts = rest.split()

        # Each month takes 2 values (rise, set), so month N is at index (N-1)*2
        idx = (month - 1) * 2
        if idx + 1 < len(parts):
            rise = parts[idx]
            set_time = parts[idx + 1]

            # Handle special cases like "----" for no rise/set
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


def main():
    """Fetch and display astronomical data for the configured month."""
    print(f"Fetching astronomical data for {YEAR}...")
    print(f"Location: {LATITUDE}°N, {LONGITUDE}°W")
    print(f"Timezone: UTC-{TIMEZONE} (EDT)")
    print()

    # Fetch all three tables
    print("Fetching sunrise/sunset table...")
    sun_html = fetch_yearly_table(0)

    print("Fetching moonrise/moonset table...")
    moon_html = fetch_yearly_table(1)

    print("Fetching astronomical twilight table...")
    twilight_html = fetch_yearly_table(4)

    if not sun_html or not moon_html or not twilight_html:
        print("Failed to fetch one or more tables.")
        return

    # Parse tables for the target month
    sun_data = parse_table(sun_html, MONTH)
    moon_data = parse_table(moon_html, MONTH)
    twilight_data = parse_table(twilight_html, MONTH)

    # Get month name
    month_names = [
        '', 'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    print()
    print(f"{'=' * 70}")
    print(f"{month_names[MONTH]} {YEAR}")
    print(f"{'=' * 70}")
    print()
    print(f"{'Day':<5} {'Sunrise':<10} {'Sunset':<10} {'Moonrise':<10} {'Moonset':<10} {'Astro Twi Start':<16} {'Astro Twi End':<14}")
    print("-" * 70)

    # Get the number of days in the month
    days_in_month = {
        1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
        7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
    }

    # Check for leap year
    if MONTH == 2 and (YEAR % 4 == 0 and (YEAR % 100 != 0 or YEAR % 400 == 0)):
        days_in_month[2] = 29

    for day in range(1, days_in_month[MONTH] + 1):
        sun = sun_data.get(day, ('N/A', 'N/A'))
        moon = moon_data.get(day, ('N/A', 'N/A'))
        twilight = twilight_data.get(day, ('N/A', 'N/A'))

        print(f"{day:<5} {sun[0]:<10} {sun[1]:<10} {moon[0]:<10} {moon[1]:<10} {twilight[0]:<16} {twilight[1]:<14}")


if __name__ == "__main__":
    main()
