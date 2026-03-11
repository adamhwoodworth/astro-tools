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

### Running Tests

```bash
uv run pytest -v
```
