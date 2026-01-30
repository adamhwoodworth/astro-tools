#!/usr/bin/env python3
"""
Calculate dates when the moon is below the horizon from sunset until at least 1 AM.
Uses US Naval Observatory RS_OneYear table for astronomical data (single request per year).
"""

import requests
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser


# Configuration
LATITUDE = 44.8
LONGITUDE = -66.96
TIMEZONE = -4  # US Eastern Daylight Time (UTC-4)
CUTOFF_HOUR = 1  # Moon must be below horizon until at least 1 AM
YEAR = 2026
MONTHS_TO_CHECK = [6, 7, 8, 9]  # June through September


class YearTableParser(HTMLParser):
    """Parse USNO year table HTML to extract astronomical data."""


    def __init__(self):
        super().__init__()
        self.in_pre = False
        self.data = ""


    def handle_starttag(self, tag, attrs):
        if tag == 'pre':
            self.in_pre = True


    def handle_endtag(self, tag):
        if tag == 'pre':
            self.in_pre = False


    def handle_data(self, data):
        if self.in_pre:
            self.data += data


def fetch_year_table(year, lat, lon, tz, task):
    """
    Fetch full year astronomical data table from USNO.

    Args:
        year: Year to fetch
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        tz: Timezone offset from UTC (negative for west)
        task: 0 for sunrise/sunset, 1 for moonrise/moonset

    Returns:
        String containing the full table data, or None if request fails
    """
    url = f"https://aa.usno.navy.mil/calculated/rstt/year?year={year}&task={task}&coords={lat},{lon}&tz={tz}&ID=AA"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        parser = YearTableParser()
        parser.feed(response.text)

        return parser.data
    except Exception as e:
        print(f"Error fetching year table for task {task}: {e}")
        return None


def parse_year_table(table_text):
    """
    Parse year table text into dictionary of data.

    Args:
        table_text: Pre-formatted table text from USNO

    Returns:
        Dictionary mapping (month, day) -> {'rise': time_str, 'set': time_str}
    """
    lines = table_text.strip().split('\n')
    data = {}

    # Find the header line with month names
    month_line_idx = None
    for i, line in enumerate(lines):
        if 'Jan.' in line and 'Dec.' in line:
            month_line_idx = i
            break

    if month_line_idx is None:
        return data

    # Skip to data rows (after Day/Rise/Set header)
    data_start = month_line_idx + 3

    # Each month takes up 11 columns (5 for rise, 5 for set, 1 for spacing)
    # Starting position after day number (position 4)
    month_width = 11

    # Parse each day's data
    for line in lines[data_start:]:
        if 'Note:' in line or 'Add one hour' in line:
            break

        # Extract day number at start of line
        if len(line) < 2:
            continue

        day_match = re.match(r'(\d{2})', line)
        if not day_match:
            continue

        day = int(day_match.group(1))

        # Process each month's data using fixed positions
        for month in range(1, 13):
            # Calculate column start position for this month
            # Day takes 2 chars, then 2 spaces, then months start at position 4
            start_pos = 4 + (month - 1) * month_width

            # Extract rise and set fields (each 5 chars with potential spaces)
            if start_pos + 10 > len(line):
                # Not enough data in line
                break

            rise_field = line[start_pos:start_pos + 5].strip()
            set_field = line[start_pos + 5:start_pos + 10].strip()

            rise_time = None
            set_time = None

            # Parse rise time
            if rise_field and len(rise_field) >= 3:
                rise_field = rise_field.replace(' ', '')
                if len(rise_field) == 4:
                    rise_time = f"{rise_field[:2]}:{rise_field[2:]}"
                elif len(rise_field) == 3:
                    rise_time = f"0{rise_field[0]}:{rise_field[1:]}"

            # Parse set time
            if set_field and len(set_field) >= 3:
                set_field = set_field.replace(' ', '')
                if len(set_field) == 4:
                    set_time = f"{set_field[:2]}:{set_field[2:]}"
                elif len(set_field) == 3:
                    set_time = f"0{set_field[0]}:{set_field[1:]}"

            data[(month, day)] = {'rise': rise_time, 'set': set_time}

    return data


def parse_time(time_str):
    """
    Parse time string in HH:MM format to minutes since midnight.

    Args:
        time_str: Time in "HH:MM" format

    Returns:
        Integer minutes since midnight
    """
    if not time_str:
        return None
    hours, minutes = map(int, time_str.split(':'))
    return hours * 60 + minutes


def check_moon_below_horizon(date, sun_data, moon_data, cutoff_hour):
    """
    Check if moon is below horizon from sunset until cutoff hour.

    Args:
        date: datetime.date object
        sun_data: Dictionary of sun rise/set times
        moon_data: Dictionary of moon rise/set times
        cutoff_hour: Hour (in 24-hour format) that moon must stay below horizon until

    Returns:
        Tuple of (bool, dict): (True if moon is below horizon from sunset until cutoff hour,
                                 dict with time data for display)
    """
    month = date.month
    day = date.day
    next_date = date + timedelta(days=1)
    next_month = next_date.month
    next_day = next_date.day

    # Get sunset time for today
    sun_today = sun_data.get((month, day), {})
    sunset = sun_today.get('set')

    if not sunset:
        return False, None

    sunset_mins = parse_time(sunset)
    cutoff_mins = cutoff_hour * 60

    # Get moon times
    moon_today = moon_data.get((month, day), {})
    moon_tomorrow = moon_data.get((next_month, next_day), {})

    moonset_today = moon_today.get('set')
    moonrise_today = moon_today.get('rise')
    moonrise_tomorrow = moon_tomorrow.get('rise')

    # Collect times for display
    times = {
        'sunset': sunset,
        'moonset_today': moonset_today or 'N/A',
        'moonrise_today': moonrise_today or 'N/A',
        'moonrise_tomorrow': moonrise_tomorrow or 'N/A'
    }

    # Case 1: Moon has already set before sunset
    if moonset_today:
        moonset_today_mins = parse_time(moonset_today)
        if moonset_today_mins < sunset_mins:
            # Moon set before sunset - check when it rises next
            # First check if it rises later today after sunset
            if moonrise_today:
                moonrise_today_mins = parse_time(moonrise_today)
                if moonrise_today_mins > sunset_mins:
                    # Moon rises in the evening (after sunset on same day) - will be visible
                    return False, times

            # Check if moon rises tomorrow morning before cutoff
            if moonrise_tomorrow:
                moonrise_tomorrow_mins = parse_time(moonrise_tomorrow)
                if moonrise_tomorrow_mins < cutoff_mins:
                    return False, times  # Moon rises before cutoff

            return True, times  # Moon stays down until at least cutoff hour

    # Case 2: Moon is up at sunset - check when it sets
    # Check if moon sets today after sunset
    if moonset_today:
        moonset_today_mins = parse_time(moonset_today)
        if moonset_today_mins > sunset_mins:
            # Moon sets tonight - check if it rises again before cutoff
            if moonrise_tomorrow:
                moonrise_tomorrow_mins = parse_time(moonrise_tomorrow)
                if moonrise_tomorrow_mins < cutoff_mins:
                    return False, times
            return True, times

    # Check if moon sets tomorrow morning before cutoff
    moonset_tomorrow = moon_tomorrow.get('set')
    if moonset_tomorrow:
        moonset_tomorrow_mins = parse_time(moonset_tomorrow)
        if moonset_tomorrow_mins < cutoff_mins:
            # Check if moon rises again before cutoff
            if moonrise_tomorrow:
                moonrise_tomorrow_mins = parse_time(moonrise_tomorrow)
                if moonrise_tomorrow_mins < cutoff_mins:
                    return False, times
            return True, times

    return False, times


def main():
    """Main function to find all qualifying dates."""
    print(f"Fetching astronomical data for {YEAR}...")
    print(f"Location: {LATITUDE}°N, {LONGITUDE}°W (Timezone: UTC{TIMEZONE:+d})")
    print()

    # Fetch year tables
    print("Fetching sunrise/sunset data...")
    sun_table = fetch_year_table(YEAR, LATITUDE, LONGITUDE, TIMEZONE, 0)
    if not sun_table:
        print("Failed to fetch sunrise/sunset data")
        return

    print("Fetching moonrise/moonset data...")
    moon_table = fetch_year_table(YEAR, LATITUDE, LONGITUDE, TIMEZONE, 1)
    if not moon_table:
        print("Failed to fetch moonrise/moonset data")
        return

    # Parse tables
    print("Parsing data tables...")
    sun_data = parse_year_table(sun_table)
    moon_data = parse_year_table(moon_table)

    print(f"\nSearching for nights when moon is below horizon from sunset until {CUTOFF_HOUR}:00 AM")
    print()

    qualifying_dates = {month: [] for month in MONTHS_TO_CHECK}
    month_names = {6: 'June', 7: 'July', 8: 'August', 9: 'September'}

    for month in MONTHS_TO_CHECK:
        print(f"Checking {month_names[month]} {YEAR}...")

        # Determine days in month
        if month in [4, 6, 9, 11]:
            days_in_month = 30
        elif month == 2:
            # Simple leap year check
            days_in_month = 29 if YEAR % 4 == 0 and (YEAR % 100 != 0 or YEAR % 400 == 0) else 28
        else:
            days_in_month = 31

        for day in range(1, days_in_month + 1):
            date = datetime(YEAR, month, day).date()

            qualifies, times = check_moon_below_horizon(date, sun_data, moon_data, CUTOFF_HOUR)

            # Display information for all dates
            status = "✓" if qualifies else "✗"
            if times:
                # Determine the relevant moonrise for this night
                sunset_mins = parse_time(times['sunset'])
                moonrise_today_mins = parse_time(times['moonrise_today']) if times['moonrise_today'] != 'N/A' else None

                # If moon rises today after sunset, that's the relevant time
                # Otherwise, use tomorrow's moonrise
                if moonrise_today_mins and moonrise_today_mins > sunset_mins:
                    moonrise_str = times['moonrise_today']
                else:
                    moonrise_str = f"{times['moonrise_tomorrow']} (next day)" if times['moonrise_tomorrow'] != 'N/A' else times['moonrise_tomorrow']

                print(f"  {status} {date.strftime('%B %d, %Y')} - Sunset: {times['sunset']}, Moonset: {times['moonset_today']}, Moonrise: {moonrise_str}")
            else:
                print(f"  {status} {date.strftime('%B %d, %Y')} - No data available")

            if qualifies:
                qualifying_dates[month].append(day)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total = 0

    for month in MONTHS_TO_CHECK:
        dates = qualifying_dates[month]
        if dates:
            date_ranges = []
            start = dates[0]
            end = dates[0]

            for i in range(1, len(dates)):
                if dates[i] == end + 1:
                    end = dates[i]
                else:
                    if start == end:
                        date_ranges.append(f"{start}")
                    else:
                        date_ranges.append(f"{start}-{end}")
                    start = dates[i]
                    end = dates[i]

            if start == end:
                date_ranges.append(f"{start}")
            else:
                date_ranges.append(f"{start}-{end}")

            print(f"\n{month_names[month]} {YEAR} ({len(dates)} nights):")
            print(f"  {month_names[month]} {', '.join(date_ranges)}")
            total += len(dates)

    print(f"\nTotal: {total} nights")


if __name__ == "__main__":
    main()
