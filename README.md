# Astro Tools

Astrophotography and night sky observation planning tools.

## Installation

```bash
uv sync

# Enable the git pre-commit hook (once per clone)
git config core.hooksPath .githooks
```

The pre-commit hook formats the staged Python files with `ruff format`, re-stages them, and blocks the commit if `ruff check` finds lint errors. A staged file that also has unstaged edits is not reformatted (that would pull the unstaged edits into the commit); if it needs formatting the commit is blocked instead. Skip the hook for one commit with `git commit --no-verify`.

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

### Example Output

```
$ uv run darknights.py 44.81,-66.95 2026 feb
Fetching astronomical data for 2026...
Location: 44.8100°N, 66.9500°W
Timezone: America/New_York (UTC-5)

Fetching sunrise/sunset table...
Fetching moonrise/moonset table...
Fetching astronomical twilight table...

February 2026
Date    Sunset    Twi End    Moon    Moon Event                 Twi Start    Dark Sky    Rating
------  --------  ---------  ------  -------------------------  -----------  ----------  ----------
Feb  1  16:36     18:17      Up      Moonset 07:19 (next day)   05:06        Never Dark
Feb  2  16:38     18:18      Up      Moonset 07:41 (next day)   05:05        Never Dark
Feb  3  16:39     18:19      Down    Moonrise 18:56             05:04        0:37
Feb  4  16:41     18:20      Down    Moonrise 20:07             05:02        1:47        ★
Feb  5  16:42     18:22      Down    Moonrise 21:16             05:01        2:54        ★★
Feb  6  16:43     18:23      Down    Moonrise 22:23             05:00        4:00        ★★★★
Feb  7  16:45     18:24      Down    Moonrise 23:30             04:59        5:06        ★★★★★
Feb  8  16:46     18:25      Down    Moonrise 00:37 (next day)  04:58        6:12        ★★★★★★
Feb  9  16:48     18:27      Down    Moonrise 01:43 (next day)  04:57        7:16        ★★★★★★★
Feb 10  16:49     18:28      Down    Moonrise 02:46 (next day)  04:55        8:18        ★★★★★★★★
Feb 11  16:50     18:29      Down    Moonrise 03:44 (next day)  04:54        9:15        ★★★★★★★★★
Feb 12  16:52     18:31      Down    Moonrise 04:33 (next day)  04:53        10:02       ★★★★★★★★★★
Feb 13  16:53     18:32      Down    Moonrise 05:14 (next day)  04:51        10:19       ★★★★★★★★★★
Feb 14  16:55     18:33      Down    Moonrise 05:47 (next day)  04:50        10:17       ★★★★★★★★★★
Feb 15  16:56     18:34      Down    Moonrise 06:13 (next day)  04:49        10:15       ★★★★★★★★★★
Feb 16  16:58     18:36      Down    Moonrise 06:35 (next day)  04:47        10:11       ★★★★★★★★★★
Feb 17  16:59     18:37      Down    Moonrise 06:55 (next day)  04:46        10:09       ★★★★★★★★★★
Feb 18  17:00     18:38      Down    Moonrise 07:14 (next day)  04:44        10:06       ★★★★★★★★★★
Feb 19  17:02     18:40      Up      Moonset 19:47              04:43        8:56        ★★★★★★★★
Feb 20  17:03     18:41      Up      Moonset 21:02              04:41        7:39        ★★★★★★★
Feb 21  17:05     18:42      Up      Moonset 22:20              04:40        6:20        ★★★★★★
Feb 22  17:06     18:44      Up      Moonset 23:40              04:38        4:58        ★★★★
Feb 23  17:07     18:45      Up      Moonset 01:00 (next day)   04:37        3:37        ★★★
Feb 24  17:09     18:46      Up      Moonset 02:15 (next day)   04:35        2:20        ★★
Feb 25  17:10     18:47      Up      Moonset 03:20 (next day)   04:33        1:13        ★
Feb 26  17:11     18:49      Up      Moonset 04:11 (next day)   04:32        0:21
Feb 27  17:13     18:50      Up      Moonset 04:50 (next day)   04:30        Never Dark
Feb 28  17:14     18:51      Up      Moonset 05:20 (next day)   04:28        Never Dark
```

## fullmoon.py

Finds prime "big moon near the horizon at golden hour" windows: every **moonrise within 61 minutes of sunset**, and every **moonset within 61 minutes of sunrise**. These are the nights to photograph a low, full-looking moon against a still-lit sky.

Uses the same US Naval Observatory data, timezone auto-detection, and `cache/` directory as `darknights.py` (the two tools share any already-downloaded sun/moon tables).

### Usage

```bash
uv run fullmoon.py <lat,long> [year] [month] [--no-color] [--no-cache]
```

The argument syntax is identical to `darknights.py`:

```bash
# Current year, all months
uv run fullmoon.py '44.85, -66.98'

# Specific year, all months
uv run fullmoon.py 44.85,-66.98 2026

# Specific year and month
uv run fullmoon.py '44.85, -66.98' 2026 jun
```

Valid months: `jan`, `feb`, `mar`, `apr`, `may`, `jun`, `jul`, `aug`, `sep`, `oct`, `nov`, `dec`

Options:
- `--no-color`: Disable ANSI color codes in output
- `--no-cache`: Bypass cache and fetch fresh data from USNO

Each qualifying event is one row. A date can appear twice when both a morning moonset-near-sunrise and an evening moonrise-near-sunset qualify (common right around the full moon); the morning event is listed first. The `Diff` column is the gap in whole minutes between the moon event and its paired sun event. The `Rating` reflects how tight that gap is — within 31 minutes is the "best" tier:

- `★★★` — within 15 minutes
- `★★` — within 31 minutes
- `★` — within 61 minutes

### Example Output

```
$ uv run fullmoon.py 44.81,-66.95 2026 jun --no-color
Finding moon/horizon windows for 2026...
Location: 44.8100°N, 66.9500°W
Timezone: America/New_York (UTC-5)

Fetching sunrise/sunset table...
Fetching moonrise/moonset table...

Moonrise↔sunset & moonset↔sunrise windows · June 2026
Date    Event              Moon    Sun      Diff  Rating
------  -----------------  ------  -----  ------  --------
Jun  1  Moonset / Sunrise  05:04   04:45      19  ★★
Jun 28  Moonrise / Sunset  19:51   20:18      27  ★★
Jun 29  Moonset / Sunrise  03:52   04:45      53  ★
Jun 29  Moonrise / Sunset  20:37   20:18      19  ★★
Jun 30  Moonset / Sunrise  04:51   04:45       6  ★★★
Jun 30  Moonrise / Sunset  21:15   20:18      57  ★
```

## tides.py

Prints a table of high and low tides for the tide prediction station nearest a location.

Uses NOAA CO-OPS for the US and its territories and the Canadian Hydrographic Service (CHS) for Canada. Neither API accepts coordinates, so the script downloads both station lists, picks the closest station by great-circle distance, and asks the API that owns it for predictions. The station lists are cached in `cache/` and re-downloaded when older than 30 days. Locations outside the US and Canada are not covered; the script warns when the nearest station is more than 50 miles away.

Times are shown in the time zone of the location you asked about, which near a border can differ from the station's. Heights are relative to the source's datum (MLLW for NOAA, chart datum for CHS), named in the table header; the two are close but not identical.

### Usage

```bash
uv run tides.py <lat,long> [year] [month] [day] [+N] [--units ft|m] [--tz ZONE] [--station ID] [--refresh] [--no-color]
```

```bash
# Today
uv run tides.py '44.85, -66.98'

# Specific year, every day
uv run tides.py 44.85,-66.98 2026

# Specific year and month
uv run tides.py '44.85, -66.98' 2026 oct

# A single day
uv run tides.py '44.85, -66.98' 2026 oct 4

# 7 days starting on a date (Aug 29 through Sep 4)
uv run tides.py 44.85,-66.98 2027 aug 29 +7

# The week starting today
uv run tides.py 44.85,-66.98 +7
```

`+N` shows N days counting from the first date of the range, that date included, so `+1` is the same as a single day. After only a year or a year and month it counts from the first day of that year or month (`2027 aug +10` is Aug 1 through Aug 10).

Valid months: `jan`, `feb`, `mar`, `apr`, `may`, `jun`, `jul`, `aug`, `sep`, `oct`, `nov`, `dec`

Options:
- `--units ft|m`: Height units (default `ft`); distances follow as miles or kilometres
- `--tz ZONE`: Display times in this zone (e.g. `America/St_Johns`) instead of the location's
- `--station ID`: Use this NOAA station id or CHS station code instead of the nearest station. Straight-line nearest can pick a station across a peninsula or up a river
- `--refresh`: Re-download the cached station lists
- `--no-color`: Disable ANSI color codes in output

### Example Output

```
$ uv run tides.py 44.81,-66.95 2026 sep 19 --no-color
Finding tide station...
  Using cached station lists
Fetching tide predictions from CHS...

Station: Welshpool (CHS 00015) — 5.5 mi from 44.8100, -66.9500
Heights in ft above chart datum, times America/New_York
Date        Time    Tide      Height
----------  ------  ------  --------
Sat Sep 19  05:28   High        18.0
Sat Sep 19  11:42   Low          6.1
Sat Sep 19  17:49   High        18.9
```

## Running Tests

```bash
uv run pytest -v
```
