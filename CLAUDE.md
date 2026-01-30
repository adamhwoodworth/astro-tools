# Moon Dark Nights Project

## Project Overview
Python script to calculate dates when the moon is below the horizon from sunset until at least 1 AM, useful for astrophotography planning.

## Running the Script

### Always use uv run
```bash
uv run moon-dark-nights.py
```

**Important**:
- Always use `uv run` to execute Python commands

## Configuration

### Location Settings
Located in `moon-dark-nights.py`:
```python
LATITUDE = 44.8
LONGITUDE = -66.96
TIMEZONE = -4  # US Eastern Daylight Time (UTC-4)
```

### Date Ranges
Modify `DATE_RANGES` list to check different months:
```python
DATE_RANGES = [
    (2026, 6, 1, 30),   # June 2026
    (2026, 7, 1, 31),   # July 2026
    # etc.
]
```

### Cutoff Hour
```python
CUTOFF_HOUR = 1  # Moon must be below horizon until at least 1 AM
```

## Data Source
Uses US Naval Observatory API:
- Endpoint: `https://aa.usno.navy.mil/api/rstt/oneday`
- Rate limiting: Script includes 0.1s delay between requests
- Returns sunrise, sunset, moonrise, and moonset times

## Output Format
- `✓` - Qualifying night (moon below horizon from sunset until cutoff)
- `✗` - Non-qualifying night
- `(next day)` - Indicates moonrise occurs after midnight
- `N/A` - Event doesn't occur on that date

## Code Structure
- `fetch_astronomical_data()` - API calls to USNO
- `check_moon_below_horizon()` - Logic to determine if night qualifies
- `main()` - Loops through date ranges and displays results
