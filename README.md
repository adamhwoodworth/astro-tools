THIS IS BROKEN MORE OR LESS
The code is not getting things right.

# Astro Tools

A collection of tools for astrophotography and night sky observation planning.

## Tools

### Moon Dark Nights (`moon-dark-nights.py`)

Calculate optimal nights for astrophotography by finding dates when the moon is below the horizon from sunset until late evening.

For astrophotography and night sky observation, moonlight can wash out faint stars, nebulae, and the Milky Way. This tool identifies nights when the moon stays below the horizon from sunset until at least 1 AM, providing ideal dark sky conditions for photography.

**Features:**
- Calculates moon visibility for any location and date range
- Uses accurate astronomical data from the US Naval Observatory
- Shows verbose output with sunset, moonset, and moonrise times for every night
- Clearly indicates which nights meet dark sky criteria
- Displays summary of qualifying date ranges

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency management.

```bash
# Install dependencies
uv sync
```

## Usage

Run the script with:

```bash
uv run moon-dark-nights.py
```

## Configuration

Edit the configuration variables at the top of `moon-dark-nights.py`:

### Location

```python
LATITUDE = 44.8      # Decimal degrees (positive for North)
LONGITUDE = -66.96   # Decimal degrees (negative for West)
TIMEZONE = -4        # UTC offset (e.g., -4 for EDT, -5 for EST)
```

### Cutoff Time

```python
CUTOFF_HOUR = 1  # Moon must stay down until this hour (1 = 1:00 AM)
```

### Date Ranges

```python
DATE_RANGES = [
    (2026, 6, 1, 30),   # (year, month, start_day, end_day)
    (2026, 7, 1, 31),
    (2026, 8, 1, 31),
    (2026, 9, 1, 30),
]
```

## Sample Output

```
Searching for nights when moon is below horizon from sunset until 1:00 AM
Location: 44.8°N, -66.96°W (Timezone: UTC-4)

Checking June 2026...
  ✗ June 01, 2026 - Sunset: 20:07, Moonset: 05:04, Moonrise: 21:54
  ✗ June 02, 2026 - Sunset: 20:08, Moonset: 05:57, Moonrise: 22:38
  ✗ June 05, 2026 - Sunset: 20:10, Moonset: 09:10, Moonrise: 00:06 (next day)
  ✓ June 08, 2026 - Sunset: 20:12, Moonset: 12:36, Moonrise: 01:03 (next day)
  ✓ June 09, 2026 - Sunset: 20:12, Moonset: 13:47, Moonrise: 01:22 (next day)
  ...

============================================================
SUMMARY
============================================================

June 2026 (21 nights):
  June 8-28

Total: 81 nights
```

### Output Legend

- `✓` - Qualifying night (moon below horizon from sunset until cutoff time)
- `✗` - Non-qualifying night (moon visible during observation period)
- `(next day)` - Moonrise occurs after midnight
- `N/A` - Event (moonrise/moonset) doesn't occur on that date

## How It Works

The script:

1. Queries the US Naval Observatory API for sun and moon rise/set times
2. For each date, determines if the moon is below the horizon from sunset until the cutoff hour
3. Considers multiple scenarios:
   - Moon sets before sunset and doesn't rise until after cutoff
   - Moon sets after sunset but doesn't rise again until after cutoff
   - Moon is already down at sunset and stays down
4. Displays detailed timing information for every night checked
5. Summarizes qualifying date ranges for easy planning

## Data Source

Astronomical data provided by the [US Naval Observatory API](https://aa.usno.navy.mil/data/api):
- Accurate sun and moon rise/set times for any location
- Times adjusted for specified timezone
- 100ms delay between requests to respect rate limits

**Use Cases:**
- Planning astrophotography sessions for Milky Way imaging
- Scheduling deep sky object photography (galaxies, nebulae)
- Finding optimal nights for meteor shower observation
- Planning dark sky camping trips
- Coordinating with new moon periods for maximum darkness

## Contributing

Additional astrophotography and observation planning tools are welcome. Each tool should be self-contained and well-documented.

## License

MIT
