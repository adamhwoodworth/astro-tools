"""
High/low tide predictions for the tide station nearest a latitude/longitude.
Used by tides.py and nightplan.py.

Neither NOAA CO-OPS (US) nor CHS IWLS (Canada) accepts coordinates, so the
station lists of both are fetched (and cached), the nearest station across
both is picked by great-circle distance, and the API that owns that station is
asked for high/low predictions. Everything is UTC internally; times are
converted to the requested location's zone for display.
"""

import json
import math
import time as time_module
from datetime import UTC, datetime, time, timedelta
from typing import NamedTuple

import requests

from astro_tools.common import (
    CACHE_DIR,
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


def add_tide_options(parser):
    """Options shared by the tools that show tides."""
    parser.add_argument("--units", choices=["ft", "m"], default="ft", help="height units (default: ft)")
    parser.add_argument("--station", help="use this NOAA id or CHS code instead of the nearest station")
    parser.add_argument("--refresh", action="store_true", help="re-download the cached station lists")


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


def tide_events_for(lat, lon, first_day, last_day, tz, station_id=None, refresh=False):
    """
    Tide events on the local dates first_day..last_day (in tz) at the station
    nearest lat/lon, or at station_id when given.

    Returns (station, distance_miles, events).
    """
    print("Finding tide station...")
    stations = load_stations(refresh)
    if station_id:
        station = find_station(station_id, stations)
        miles = haversine_miles(lat, lon, station.lat, station.lon)
    else:
        station, miles = nearest_station(lat, lon, stations)

    start, end = local_window(first_day, last_day, tz)
    print(f"Fetching tide predictions from {station.source}...")
    return station, miles, events_in_window(fetch_events(station, start, end), start, end)
