# Astro Tools

Astrophotography and night sky observation planning tools.

## Installation

```bash
uv sync
```

## darknights.py

Displays astronomical data for planning astrophotography sessions. Shows sunset, twilight times, moon state, and dark sky duration for each night of a specified month.

Uses data from the US Naval Observatory to calculate when the moon is below the horizon during astronomical twilight, helping identify the best nights for imaging.

### Usage

```bash
uv run darknights.py <year> <month> [--no-color]
```

Examples:
```bash
uv run darknights.py 2026 jun
uv run darknights.py 2026 jul --no-color
```

Valid months: `jan`, `feb`, `mar`, `apr`, `may`, `jun`, `jul`, `aug`, `sep`, `oct`, `nov`, `dec`

### Running Tests

```bash
uv run pytest tests/ -v
```

### Configuration

Edit location settings in `darknights.py`:

```python
LATITUDE = 44.81
LONGITUDE = -66.95
TIMEZONE = 4  # Hours west of Greenwich
```
