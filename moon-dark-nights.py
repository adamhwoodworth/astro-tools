#!/usr/bin/env python3
"""
Calculate dates when the moon is below the horizon from sunset until at least 1 AM.
Uses US Naval Observatory API for astronomical data.
"""

import requests
import json
import time
from datetime import datetime, timedelta


# Configuration
LATITUDE = 44.8
LONGITUDE = -66.96
TIMEZONE = -4  # US Eastern Daylight Time (UTC-4)
CUTOFF_HOUR = 1  # Moon must be below horizon until at least 1 AM

# Date ranges to check (year, month, start_day, end_day)
DATE_RANGES = [
    (2026, 6, 1, 30),   # June 2026
    (2026, 7, 1, 31),   # July 2026
    (2026, 8, 1, 31),   # August 2026
    (2026, 9, 1, 30),   # September 2026
]


def fetch_astronomical_data(date_str, lat, lon, tz):
    """
    Fetch sunrise, sunset, moonrise, and moonset times from USNO API.

    Args:
        date_str: Date string in format "YYYY-M-D"
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        tz: Timezone offset from UTC (negative for west)

    Returns:
        Dictionary with sun and moon event times, or None if request fails
    """
    url = f"https://aa.usno.navy.mil/api/rstt/oneday?date={date_str}&coords={lat},{lon}&tz={tz}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        time.sleep(0.1)  # Delay to avoid rate limiting
        return data
    except Exception as e:
        print(f"Error fetching data for {date_str}: {e}")
        return None


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


def get_event_time(data, event_type, event_name):
    """
    Extract event time from USNO API response.

    Args:
        data: API response dictionary
        event_type: "sundata" or "moondata"
        event_name: Event name like "rise", "set"

    Returns:
        Time string or None if event doesn't occur
    """
    if not data:
        return None

    # Navigate to properties.data
    if 'properties' not in data or 'data' not in data['properties']:
        return None

    inner_data = data['properties']['data']
    if event_type not in inner_data:
        return None

    events = inner_data[event_type]
    for event in events:
        if event.get('phen', '').lower() == event_name.lower():
            return event.get('time')

    return None


def check_moon_below_horizon(date, lat, lon, tz, cutoff_hour):
    """
    Check if moon is below horizon from sunset until cutoff hour.

    Args:
        date: datetime.date object
        lat: Latitude
        lon: Longitude
        tz: Timezone offset
        cutoff_hour: Hour (in 24-hour format) that moon must stay below horizon until

    Returns:
        Tuple of (bool, dict): (True if moon is below horizon from sunset until cutoff hour,
                                 dict with time data for display)
    """
    date_str = f"{date.year}-{date.month}-{date.day}"
    next_date = date + timedelta(days=1)
    next_date_str = f"{next_date.year}-{next_date.month}-{next_date.day}"

    # Fetch data for current day and next day
    data_today = fetch_astronomical_data(date_str, lat, lon, tz)
    data_tomorrow = fetch_astronomical_data(next_date_str, lat, lon, tz)

    if not data_today:
        return False, None

    # Get sunset time for today
    sunset = get_event_time(data_today, 'sundata', 'set')
    if not sunset:
        return False, None

    sunset_mins = parse_time(sunset)
    cutoff_mins = cutoff_hour * 60  # Convert cutoff hour to minutes since midnight

    # Get moonset time for today
    moonset_today = get_event_time(data_today, 'moondata', 'set')

    # Get moonrise times
    moonrise_today = get_event_time(data_today, 'moondata', 'rise')
    moonrise_tomorrow = get_event_time(data_tomorrow, 'moondata', 'rise') if data_tomorrow else None

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
    moonset_tomorrow = get_event_time(data_tomorrow, 'moondata', 'set')
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
    qualifying_dates = {6: [], 7: [], 8: [], 9: []}

    print(f"Searching for nights when moon is below horizon from sunset until {CUTOFF_HOUR}:00 AM")
    print(f"Location: {LATITUDE}°N, {LONGITUDE}°W (Timezone: UTC{TIMEZONE:+d})")
    print()

    for year, month, start_day, end_day in DATE_RANGES:
        print(f"Checking {datetime(year, month, 1).strftime('%B %Y')}...")

        for day in range(start_day, end_day + 1):
            date = datetime(year, month, day).date()

            qualifies, times = check_moon_below_horizon(date, LATITUDE, LONGITUDE, TIMEZONE, CUTOFF_HOUR)

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

    month_names = {6: 'June', 7: 'July', 8: 'August', 9: 'September'}
    total = 0

    for month in [6, 7, 8, 9]:
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

            print(f"\n{month_names[month]} 2026 ({len(dates)} nights):")
            print(f"  {month_names[month]} {', '.join(date_ranges)}")
            total += len(dates)

    print(f"\nTotal: {total} nights")


if __name__ == "__main__":
    main()
