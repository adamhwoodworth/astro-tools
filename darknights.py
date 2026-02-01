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


def get_moon_state_at_sunset(sunset, moonrise, moonset, next_day_moonrise, next_day_moonset):
    """
    Determine if moon is up or down at sunset.

    Returns tuple: (state, moonset_info) where moonset_info is (time, is_next_day) or None
    """
    sunset_mins = time_to_minutes(sunset)
    if sunset_mins is None:
        return ('Unknown', None)

    moonrise_mins = time_to_minutes(moonrise)
    moonset_mins = time_to_minutes(moonset)
    next_moonrise_mins = time_to_minutes(next_day_moonrise)
    next_moonset_mins = time_to_minutes(next_day_moonset)

    # Determine moon state at sunset
    # Moon is Up if: moonrise occurred before sunset AND (moonset is after sunset OR no moonset today)
    # Moon is Down if: moonset occurred before sunset AND (moonrise is after sunset OR no moonrise today)

    if moonrise_mins is not None and moonset_mins is not None:
        if moonrise_mins < moonset_mins:
            # Normal day: rise then set
            if moonrise_mins <= sunset_mins < moonset_mins:
                return ('Up', (moonset, False))
            else:
                return ('Down', None)
        else:
            # Moonset before moonrise (moon was up from previous day)
            if sunset_mins < moonset_mins:
                return ('Up', (moonset, False))
            elif sunset_mins >= moonrise_mins:
                # Find when moon sets (next day)
                if next_moonset_mins is not None:
                    return ('Up', (next_day_moonset, True))
                return ('Up', ('N/A', False))
            else:
                return ('Down', None)

    elif moonrise_mins is not None and moonset_mins is None:
        # Moonrise but no moonset today - moon sets next day
        if moonrise_mins <= sunset_mins:
            if next_moonset_mins is not None:
                return ('Up', (next_day_moonset, True))
            return ('Up', ('N/A', False))
        else:
            return ('Down', None)

    elif moonrise_mins is None and moonset_mins is not None:
        # Moonset but no moonrise today - moon was up from previous day
        if sunset_mins < moonset_mins:
            return ('Up', (moonset, False))
        else:
            return ('Down', None)

    else:
        # No moonrise or moonset - moon either up or down all day
        # Check next day to infer
        if next_moonrise_mins is not None and next_moonset_mins is not None:
            if next_moonrise_mins < next_moonset_mins:
                return ('Down', None)
            else:
                return ('Up', (next_day_moonset, True))
        return ('Unknown', None)


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

    # Parse tables for the target month and next month (for next-day moonset)
    sun_data = parse_table(sun_html, MONTH)
    moon_data = parse_table(moon_html, MONTH)
    twilight_data = parse_table(twilight_html, MONTH)

    next_month = MONTH + 1 if MONTH < 12 else 1
    next_moon_data = parse_table(moon_html, next_month)

    # Get month name
    month_names = [
        '', 'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    # Get the number of days in the month
    days_in_month = {
        1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
        7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
    }

    # Check for leap year
    if MONTH == 2 and (YEAR % 4 == 0 and (YEAR % 100 != 0 or YEAR % 400 == 0)):
        days_in_month[2] = 29

    print()
    print(f"{'=' * 70}")
    print(f"{month_names[MONTH]} {YEAR}")
    print(f"{'=' * 70}")
    print()

    for day in range(1, days_in_month[MONTH] + 1):
        sun = sun_data.get(day, ('N/A', 'N/A'))
        moon = moon_data.get(day, ('N/A', 'N/A'))
        twilight = twilight_data.get(day, ('N/A', 'N/A'))

        # Get next day's moon data
        next_day = day + 1
        if next_day > days_in_month[MONTH]:
            next_moon = next_moon_data.get(1, ('N/A', 'N/A'))
        else:
            next_moon = moon_data.get(next_day, ('N/A', 'N/A'))

        sunset = sun[1]
        moonrise = moon[0]
        moonset = moon[1]
        twilight_end = twilight[1]

        moon_state, moonset_info = get_moon_state_at_sunset(
            sunset, moonrise, moonset, next_moon[0], next_moon[1]
        )

        # Build output line
        line = f"{month_names[MONTH][:3]} {day:2d}: Sunset {sunset}  Moon {moon_state:<4}  Twilight ends {twilight_end}"

        if moon_state == 'Up' and moonset_info:
            moonset_time, is_next_day = moonset_info
            if is_next_day:
                line += f"  Moonset {moonset_time} (next day)"
            else:
                line += f"  Moonset {moonset_time}"

        print(line)


if __name__ == "__main__":
    main()
