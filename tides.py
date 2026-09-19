#!/usr/bin/env python3
"""
Print a table of high/low tide predictions for the tide station nearest a
latitude/longitude.

Neither NOAA CO-OPS (US) nor CHS IWLS (Canada) accepts coordinates, so the
station lists of both are fetched (and cached), the nearest station across
both is picked by great-circle distance, and the API that owns that station is
asked for high/low predictions. Everything is UTC internally; times are
converted to the requested location's zone for display.
"""

import argparse
import calendar
import json
import math
import re
import sys
import time as time_module
from datetime import UTC, date, datetime, time, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from tabulate import tabulate
from timezonefinder import TimezoneFinder

from astro_common import (
    BG_DARK_BLUE,
    BG_LIGHT_BLUE,
    CACHE_DIR,
    HEADER_BG,
    HEADER_FG,
    MONTH_ABBREVS,
    RESET,
    TEXT_FG,
    parse_latlong,
)

NOAA_STATIONS_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
NOAA_DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
CHS_BASE_URL = "https://api-iwls.dfo-mpo.gc.ca/api/v1"
USER_AGENT = "astro-tools/tides.py"
REQUEST_TIMEOUT = 30

STATIONS_CACHE_FILE = CACHE_DIR / "tides_stations.json"
STATIONS_MAX_AGE_DAYS = 30

# CHS rejects requests spanning more than 366 days
CHS_MAX_SPAN_DAYS = 180

# Events fetched either side of the display window, so every displayed CHS
# event has a neighbour to be labelled against
FETCH_PADDING = timedelta(days=1)

EARTH_RADIUS_MILES = 3958.8
FEET_PER_METRE = 3.28084
KM_PER_MILE = 1.609344
FAR_STATION_MILES = 50

DATUMS = {"NOAA": "MLLW", "CHS": "chart datum"}

# The +N day-count argument, e.g. +7
DAYS_ARG = re.compile(r"\+\d+")

# CHS time series holding high/low tide predictions
CHS_HILO = "wlp-hilo"


class TideError(Exception):
    """A tide API reported a problem or returned nothing usable."""


class Station(NamedTuple):
    source: str  # "NOAA" or "CHS"
    id: str  # id the owning API expects
    display_id: str  # id people recognise (CHS: the 5-digit code)
    name: str
    lat: float
    lon: float


class TideEvent(NamedTuple):
    time: datetime  # UTC
    kind: str  # "High" or "Low"
    metres: float  # above the source's datum


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points, in statute miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def normalise_noaa_stations(data):
    """Station list from NOAA's stations.json response."""
    stations = []
    for s in data["stations"]:
        name = f"{s['name']}, {s['state']}" if s.get("state") else s["name"]
        stations.append(Station("NOAA", s["id"], s["id"], name, s["lat"], s["lng"]))
    return stations


def normalise_chs_stations(data):
    """
    Station list from the CHS /stations response.

    Stations without a high/low prediction series are dropped, otherwise the
    nearest station may have no tides to show.
    """
    return [
        Station("CHS", s["id"], s["code"], s["officialName"], s["latitude"], s["longitude"])
        for s in data
        if any(ts["code"] == CHS_HILO for ts in s["timeSeries"])
    ]


def nearest_station(lat, lon, stations):
    """Return (station, distance_miles) for the station closest to lat/lon."""
    station = min(stations, key=lambda s: haversine_miles(lat, lon, s.lat, s.lon))
    return station, haversine_miles(lat, lon, station.lat, station.lon)


def label_hilo(values):
    """
    Label alternating tide heights as "High" or "Low".

    CHS does not say which events are highs. An event is a High if it is above
    its neighbour (the following event, or the previous one for the last
    event). A lone event has no neighbour and is labelled "?".
    """
    if len(values) < 2:
        return ["?"] * len(values)

    labels = []
    for i, value in enumerate(values):
        neighbour = values[i + 1] if i + 1 < len(values) else values[i - 1]
        labels.append("High" if value > neighbour else "Low")
    return labels


def parse_noaa_predictions(data):
    """
    Tide events from a NOAA datagetter response requested with time_zone=gmt
    and units=metric. NOAA reports errors as HTTP 200 with an "error" body.
    """
    if "error" in data:
        raise TideError(data["error"]["message"].strip())

    kinds = {"H": "High", "L": "Low"}
    return [
        TideEvent(
            datetime.strptime(p["t"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC),
            kinds[p["type"]],
            float(p["v"]),
        )
        for p in data["predictions"]
    ]


def parse_chs_predictions(data):
    """
    Tide events from one or more concatenated CHS wlp-hilo responses.

    Events are sorted and de-duplicated (adjacent request chunks share a
    boundary instant) before the High/Low labels are inferred.
    """
    heights = {datetime.fromisoformat(p["eventDate"]): p["value"] for p in data}
    times = sorted(heights)
    labels = label_hilo([heights[t] for t in times])
    return [TideEvent(t, label, heights[t]) for t, label in zip(times, labels)]


def resolve_date_range(year, month, day, today, days=None):
    """
    First and last local dates to display (inclusive).

    No arguments means today; a year means the whole year; year and month the
    whole month; year, month and day that single day. A days count instead
    runs that many days from the first of those dates, the first included.
    Raises ValueError for a day that does not exist.
    """
    if year is None:
        first, last = today, today
    elif month is None:
        first, last = date(year, 1, 1), date(year, 12, 31)
    elif day is None:
        first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    else:
        first, last = date(year, month, day), date(year, month, day)

    if days is not None:
        last = first + timedelta(days=days - 1)
    return first, last


def local_window(start_date, end_date, tz):
    """UTC instants [start, end) covering the local dates start_date..end_date in tz."""
    start = datetime.combine(start_date, time.min, tzinfo=tz)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def events_in_window(events, start, end):
    """Events with start <= time < end."""
    return [e for e in events if start <= e.time < end]


def date_chunks(start, end, max_days):
    """Split [start, end] into contiguous (from, to) spans of at most max_days."""
    chunks = []
    while start < end:
        stop = min(start + timedelta(days=max_days), end)
        chunks.append((start, stop))
        start = stop
    return chunks


def find_station(station_id, stations):
    """Station whose API id or display id is station_id (the --station override)."""
    for station in stations:
        if station_id in (station.id, station.display_id):
            return station
    raise TideError(f"no tide prediction station with id '{station_id}'")


def build_rows(events, tz, units):
    """Table rows [date, time, tide, height] in the display zone and units."""
    rows = []
    for event in events:
        local = event.time.astimezone(tz)
        # round() first, and add 0.0, so a height just below zero prints as "0.0" rather than "-0.0"
        if units == "ft":
            height = f"{round(event.metres * FEET_PER_METRE, 1) + 0.0:.1f}"
        else:
            height = f"{round(event.metres, 2) + 0.0:.2f}"
        rows.append([local.strftime("%a %b %d"), local.strftime("%H:%M"), event.kind, height])
    return rows


def header_lines(station, miles, lat, lon, units, tz_name):
    """Lines describing the chosen station, printed above the table."""
    distance = f"{miles:.1f} mi" if units == "ft" else f"{miles * KM_PER_MILE:.1f} km"
    lines = [
        f"Station: {station.name} ({station.source} {station.display_id}) — {distance} from {lat:.4f}, {lon:.4f}",
        f"Heights in {units} above {DATUMS[station.source]}, times {tz_name}",
    ]
    if miles > FAR_STATION_MILES:
        lines.append(f"Warning: the nearest station is {distance} away; its tides may be a poor match.")
    return lines


def year_arg(value):
    if not value.isdigit() or len(value) != 4:
        raise argparse.ArgumentTypeError(f"year must be 4 digits, got '{value}'")
    return int(value)


def month_arg(value):
    if value.lower() not in MONTH_ABBREVS:
        raise argparse.ArgumentTypeError(f"month must be one of {', '.join(MONTH_ABBREVS)}, got '{value}'")
    return MONTH_ABBREVS[value.lower()]


def parse_cli(argv):
    """Parse and validate command line arguments."""
    parser = argparse.ArgumentParser(
        usage="%(prog)s <lat,long> [year] [month] [day] [+N] [options]",
        description="High/low tide table for the tide station nearest a location. "
        "With no date, shows today; a year, year and month, or year, month and day narrow the range. "
        "+N (e.g. +7) shows N days counting from the first of those dates.",
    )
    parser.add_argument("year", nargs="?", type=year_arg, help="4-digit year")
    parser.add_argument("month", nargs="?", type=month_arg, help="3-letter abbreviation, e.g. oct")
    parser.add_argument("day", nargs="?", type=int, help="day of the month")
    parser.add_argument("--units", choices=["ft", "m"], default="ft", help="height units (default: ft)")
    parser.add_argument("--tz", help="display time zone, e.g. America/St_Johns (default: the location's)")
    parser.add_argument("--station", help="use this NOAA id or CHS code instead of the nearest station")
    parser.add_argument("--refresh", action="store_true", help="re-download the cached station lists")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI color codes in output")

    # The coordinates are pulled out first: a southern latitude ("-14.28,-170.69")
    # starts with a minus sign, which argparse would take for an option.
    index = next((i for i, arg in enumerate(argv) if "," in arg), None)
    if index is None:
        parser.error("lat,long is required, e.g. '44.85, -66.98' or 44.85,-66.98")
    latlong = argv[index]
    argv = argv[:index] + argv[index + 1 :]

    # So is the +N day count, which argparse has no positional syntax for.
    days = None
    index = next((i for i, arg in enumerate(argv) if DAYS_ARG.fullmatch(arg)), None)
    if index is not None:
        days = int(argv[index])
        if days < 1:
            parser.error(f"+N must be at least +1, got '{argv[index]}'")
        argv = argv[:index] + argv[index + 1 :]

    args = parser.parse_args(argv)
    args.lat, args.lon = parse_latlong(latlong)
    args.days = days
    return args


def cache_is_fresh(fetched, now):
    """Whether a station list fetched at ISO timestamp `fetched` is still usable."""
    return now - datetime.fromisoformat(fetched) < timedelta(days=STATIONS_MAX_AGE_DAYS)


def get_json(url, params, get=requests.get, sleep=time_module.sleep):
    """GET a JSON document, waiting and retrying once if rate limited (HTTP 429)."""
    for attempt in range(2):
        response = get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if response.status_code == 429 and attempt == 0:
            sleep(int(response.headers.get("Retry-After", 5)))
            continue
        if response.status_code != 200:
            raise TideError(f"HTTP {response.status_code} from {url}")
        return response.json()


def load_stations(refresh):
    """All NOAA and CHS tide prediction stations, from cache when fresh."""
    if not refresh and STATIONS_CACHE_FILE.exists():
        cached = json.loads(STATIONS_CACHE_FILE.read_text())
        if cache_is_fresh(cached["fetched"], datetime.now(UTC)):
            print("  Using cached station lists")
            return [Station(*fields) for fields in cached["stations"]]

    print("  Downloading station lists from NOAA and CHS...")
    stations = normalise_noaa_stations(get_json(NOAA_STATIONS_URL, {"type": "tidepredictions"}))
    stations += normalise_chs_stations(get_json(f"{CHS_BASE_URL}/stations", {}))

    CACHE_DIR.mkdir(exist_ok=True)
    STATIONS_CACHE_FILE.write_text(json.dumps({"fetched": datetime.now(UTC).isoformat(), "stations": stations}))
    print("  Saved to cache")
    return stations


def fetch_events(station, start, end):
    """Tide events from the station's own API covering at least [start, end) UTC."""
    start, end = start - FETCH_PADDING, end + FETCH_PADDING

    if station.source == "NOAA":
        params = {
            "product": "predictions",
            "station": station.id,
            "begin_date": start.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
            "datum": "MLLW",
            "interval": "hilo",
            "units": "metric",
            "time_zone": "gmt",
            "format": "json",
            "application": USER_AGENT,
        }
        return parse_noaa_predictions(get_json(NOAA_DATA_URL, params))

    data = []
    for chunk_start, chunk_end in date_chunks(start, end, CHS_MAX_SPAN_DAYS):
        params = {
            "time-series-code": CHS_HILO,
            "from": chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        data += get_json(f"{CHS_BASE_URL}/stations/{station.id}/data", params)
    return parse_chs_predictions(data)


def group_days(rows):
    """
    Make each day read as one block.

    Returns (rows, bands): the rows with the date kept only on the first row
    of each day, and a 0/1 band per row that flips whenever the day changes.
    """
    grouped = []
    bands = []
    previous_date = None
    band = 1
    for row in rows:
        if row[0] != previous_date:
            band = 1 - band
            previous_date = row[0]
            grouped.append(row)
        else:
            grouped.append(["", *row[1:]])
        bands.append(band)
    return grouped, bands


def display(rows, header, colors):
    """
    Render the station header and tide rows as a single colored table, with
    the background striped by day rather than by row.
    """
    reset, bg_dark, bg_light, header_bg, header_fg, text_fg = colors

    rows, bands = group_days(rows)
    table_str = tabulate(
        rows,
        headers=["Date", "Time", "Tide", "Height"],
        tablefmt="simple",
        disable_numparse=True,
        colalign=("left", "left", "left", "right"),
    )
    lines = table_str.split("\n")

    max_width = max(len(line) for line in lines + header)

    for line in header + lines[:2]:
        print(f"{header_bg}{header_fg}{line:<{max_width}}{reset}")

    for line, band in zip(lines[2:], bands):
        bg = bg_dark if band == 0 else bg_light
        print(f"{bg}{text_fg}{line:<{max_width}}{reset}")


def main():
    """Find the nearest tide station and display its high/low tides."""
    args = parse_cli(sys.argv[1:])

    try:
        print("Finding tide station...")
        stations = load_stations(args.refresh)
        if args.station:
            station = find_station(args.station, stations)
            miles = haversine_miles(args.lat, args.lon, station.lat, station.lon)
        else:
            station, miles = nearest_station(args.lat, args.lon, stations)

        # Times are shown in the zone of the requested location (not the
        # station's, which can differ across a border) unless overridden; a
        # location the zone lookup cannot place falls back to this machine's zone.
        tz_name = args.tz or TimezoneFinder().timezone_at(lat=args.lat, lng=args.lon)
        if tz_name:
            tz = ZoneInfo(tz_name)
        else:
            tz = datetime.now().astimezone().tzinfo
            tz_name = str(tz)

        first_day, last_day = resolve_date_range(args.year, args.month, args.day, datetime.now(tz).date(), args.days)
        start, end = local_window(first_day, last_day, tz)

        print(f"Fetching tide predictions from {station.source}...")
        events = events_in_window(fetch_events(station, start, end), start, end)
    except ZoneInfoNotFoundError:
        print(f"Error: unknown time zone '{args.tz}'", file=sys.stderr)
        sys.exit(1)
    except (TideError, ValueError, requests.RequestException) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.no_color:
        colors = ("", "", "", "", "", "")
    else:
        colors = (RESET, BG_DARK_BLUE, BG_LIGHT_BLUE, HEADER_BG, HEADER_FG, TEXT_FG)

    print()
    header = header_lines(station, miles, args.lat, args.lon, args.units, tz_name)
    if not events:
        print("\n".join(header))
        print("No tide predictions were found for the requested dates.")
        return
    display(build_rows(events, tz, args.units), header, colors)


if __name__ == "__main__":
    main()
