# Astro Tools Project

## Project Overview
Collection of Python tools for astrophotography and night sky observation planning.

## Tools

### darknights.py
Displays astronomical data for astrophotography planning, showing sunset, twilight, moon state, and dark sky duration for each night of a specified month.

## Running Tools

### Always use uv run
```bash
uv run darknights.py <year> <month>
```

### Examples
```bash
uv run darknights.py 2026 jun
uv run darknights.py 2026 jul --no-color
uv run darknights.py 2026 aug --no-cache
```

## Configuration

### Location Settings
Located in `darknights.py`:
```python
LATITUDE = 44.81
LONGITUDE = -66.95
TIMEZONE = 4  # Hours west of Greenwich (EDT = UTC-4)
```

### Command Line Arguments
- `year`: 4-digit year (e.g., 2026)
- `month`: 3-letter lowercase abbreviation (jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec)
- `--no-color`: Optional flag to disable ANSI color codes in output
- `--no-cache`: Optional flag to bypass cache for HTTP requests

## Data Source
Uses US Naval Observatory yearly tables API:
- Endpoint: `https://aa.usno.navy.mil/calculated/rstt/year`
- Returns sunrise/sunset, moonrise/moonset, and astronomical twilight times
- Fetches three separate tables per run
- Results are cached in `cache/` directory to avoid repeated requests
- Cache filenames based on MD5 hash of request parameters

## Output Format
Displays a table with:
- **Date**: Day of the month
- **Sunset**: Sunset time
- **Twi End**: End of astronomical twilight
- **Moon**: Moon state at twilight end (Up/Down)
- **Moon Event**: Next moonrise or moonset with time
- **Twi Start**: Start of next morning's twilight
- **Dark Sky**: Duration of moonless dark sky
- **Rating**: Star rating (★) for each hour of dark sky

## Testing

Run tests with:
```bash
uv run pytest tests/ -v
```
