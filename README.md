# Astro Tools

Astrophotography and night sky observation planning tools.

## Installation

```bash
uv sync
```

## darknights.py

Displays astronomical data for planning astrophotography sessions. Shows sunset, twilight times, moon state, and dark sky duration for each night.

Uses data from the US Naval Observatory to calculate when the moon is below the horizon during astronomical twilight, helping identify the best nights for imaging.

Timezone is automatically determined from the provided coordinates.

### Usage

```bash
uv run darknights.py <lat,long> [year] [month] [--no-color] [--no-cache]
```

The `lat,long` argument accepts coordinates as copied from Google Maps:
```bash
# Quoted with space (as pasted from Google Maps)
uv run darknights.py '44.85, -66.98'

# No space, no quotes needed
uv run darknights.py 44.85,-66.98
```

Examples:
```bash
# Current year, all months
uv run darknights.py '44.85, -66.98'

# Specific year, all months
uv run darknights.py 44.85,-66.98 2026

# Specific year and month
uv run darknights.py '44.85, -66.98' 2026 jun
```

Valid months: `jan`, `feb`, `mar`, `apr`, `may`, `jun`, `jul`, `aug`, `sep`, `oct`, `nov`, `dec`

Options:
- `--no-color`: Disable ANSI color codes in output
- `--no-cache`: Bypass cache and fetch fresh data from USNO

### Running Tests

```bash
uv run python -m pytest tests/ -v
```
