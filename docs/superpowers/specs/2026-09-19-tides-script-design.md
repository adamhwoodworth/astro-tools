# Tide table script — API notes and spec

Goal: a Python CLI that takes latitude/longitude, finds the closest tide prediction station, and prints a table of high/low tides.

Everything marked **verified** was checked with live requests on 2026-09-19. Everything else is from memory and should be confirmed before relying on it.

## Approach

Neither of the two recommended APIs accepts coordinates. Each publishes a station list with latitude/longitude, so the script must:

1. Fetch (and cache) the station lists from NOAA and CHS.
2. Compute the great-circle (haversine) distance from the input point to every station.
3. Pick the nearest station across both lists.
4. Call the API that owns that station for high/low predictions.
5. Print a table: local date/time, High/Low, height.

Cache the station lists on disk (they rarely change; NOAA's is several MB). Refresh when older than ~30 days or on a `--refresh` flag.

## Sources

| Source             | Coverage           | Key / cost                      | Coordinate lookup                                    |
| ------------------ | ------------------ | ------------------------------- | ---------------------------------------------------- |
| **NOAA CO-OPS**    | US and territories | None, free                      | Station list has `lat` / `lng` (3,499 stations)      |
| **CHS IWLS**       | Canada             | None, free                      | Station list has `latitude` / `longitude` (1,575)    |
| UK Admiralty Tidal | UK                 | Free tier, key needed           | Station list with coordinates                        |
| WorldTides         | Global             | Paid credits, key needed        | Takes coordinates directly, returns high/low tides   |
| Stormglass         | Global             | Key needed, ~10 requests/day    | Takes coordinates directly                           |
| Open-Meteo Marine  | Global             | None, free                      | Takes coordinates; modelled sea level, not a station |

Only NOAA and CHS are verified. Start with those two; add WorldTides later only if locations outside the US and Canada are needed.

## NOAA CO-OPS (verified)

### Station list

```
GET https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=tidepredictions
```

Response: `{ "count": 3499, "stations": [ ... ] }`. Relevant fields per station:

```json
{
	"id": "8418150",
	"name": "PORTLAND",
	"state": "ME",
	"lat": 43.65805555555556,
	"lng": -70.24416666666667,
	"type": "R",
	"reference_id": "",
	"timezonecorr": -5
}
```

- `type` is `R` (reference/harmonic station) or `S` (subordinate station).
- `S` stations only support `interval=hilo`. `R` stations also support `interval=6`, `h`, etc. Since this script only needs high/low, `hilo` works for both.
- `timezonecorr` is the standard-time UTC offset in hours (no DST). Not needed if you request `time_zone=lst_ldt`.

### Predictions

```
GET https://api.tidesandcurrents.noaa.gov/api/prod/datagetter
    ?product=predictions
    &station=8418150
    &begin_date=20260919
    &end_date=20260921
    &datum=MLLW
    &interval=hilo
    &units=english
    &time_zone=lst_ldt
    &format=json
    &application=<your-app-name>
```

Response:

```json
{
	"predictions": [
		{ "t": "2026-09-19 05:56", "v": "7.593", "type": "H" },
		{ "t": "2026-09-19 11:44", "v": "2.291", "type": "L" },
		{ "t": "2026-09-19 18:05", "v": "8.54", "type": "H" }
	]
}
```

- `t` is a naive local timestamp when `time_zone=lst_ldt` (station local time with DST). Other options: `gmt`, `lst`.
- `v` is a **string**; height in feet (`units=english`) or metres (`units=metric`) above the datum.
- `type` is `H` or `L`.
- Dates are `yyyyMMdd`. `range=<hours>` can replace `end_date`.
- `application` is an optional courtesy identifier.

Errors come back as HTTP 200 with a body like:

```json
{ "error": { "message": "No Predictions data was found. Please make sure the Datum input is valid." } }
```

So check for an `error` key, not just the status code.

## CHS IWLS — Canada (verified)

Base: `https://api-iwls.dfo-mpo.gc.ca/api/v1`

### Station list

```
GET /stations
```

Response is a bare JSON array (1,575 stations). Each station:

```json
{
	"id": "5cebf1e33d0f4a073c4bc176",
	"code": "00905",
	"officialName": "St. Johns",
	"alternativeName": "St. John's",
	"latitude": 47.567045,
	"longitude": -52.702311,
	"operating": true,
	"type": "PERMANENT",
	"timeSeries": [
		{ "code": "wlo", "nameEn": "Water level official value" },
		{ "code": "wlp", "nameEn": "Water level predictions" },
		{ "code": "wlp-hilo", "nameEn": "High and Low Tide Predictions" }
	]
}
```

- **Filter to stations whose `timeSeries` contains `code == "wlp-hilo"`** before picking the nearest (1,080 of 1,575 qualify). Otherwise the nearest station may have no tide predictions.
- The API uses the long hex `id`, not the 5-digit `code`.
- `operating: false` stations can still have predictions (predictions are computed, not observed).
- There is **no time zone field** on the station.

### Predictions

```
GET /stations/{id}/data?time-series-code=wlp-hilo&from=2026-09-19T00:00:00Z&to=2026-09-20T00:00:00Z
```

Response:

```json
[
	{ "eventDate": "2026-09-19T02:52:00Z", "qcFlagCode": "1", "value": 0.945 },
	{ "eventDate": "2026-09-19T08:29:00Z", "qcFlagCode": "1", "value": 0.704 },
	{ "eventDate": "2026-09-19T15:41:00Z", "qcFlagCode": "1", "value": 1.165 },
	{ "eventDate": "2026-09-19T23:29:00Z", "qcFlagCode": "1", "value": 0.764 }
]
```

- `from` / `to` are ISO 8601 UTC. `eventDate` is UTC.
- `value` is a number, in **metres above chart datum**.
- **Events are not labelled high or low.** Infer it: an event is High if its value is greater than its neighbour's, Low otherwise (they alternate). Fetch a few hours of padding on each side of the requested window so the first and last events have a neighbour to compare with, then trim.
- **Verified 2026-09-19:** a `wlp-hilo` request may span at most 366 days; a longer one returns HTTP 400 (`date interval should not be bigger than 366 days`). `tides.py` chunks at 180 days. Not verified: the rate limit. `tides.py` retries once on HTTP 429.

## Differences the script has to reconcile

| Aspect         | NOAA                                  | CHS                                        |
| -------------- | ------------------------------------- | ------------------------------------------ |
| Station id     | 7-digit string                        | 24-char hex `id`                           |
| Coord fields   | `lat`, `lng`                          | `latitude`, `longitude`                    |
| Times          | Local (with `lst_ldt`), naive string  | UTC, ISO 8601                              |
| Heights        | String; feet or metres via `units`    | Number; metres only                        |
| Datum          | MLLW (requested)                      | Chart datum (roughly lowest normal tide)   |
| High/low label | `type`: `H` / `L`                     | Not provided, infer from neighbours        |
| Errors         | HTTP 200 with `{"error": {...}}`      | HTTP status codes                          |

Time zones: simplest consistent approach is to request NOAA with `time_zone=gmt` too, treat everything as UTC internally, and convert for display. To find the station's zone from its coordinates use the `timezonefinder` package with the stdlib `zoneinfo`; also offer a `--tz` override (e.g. `America/St_Johns`) and fall back to the machine's local zone.

Units: normalise to one unit for display (`--units ft|m`, 1 m = 3.28084 ft). Print the datum in the table header, since MLLW and chart datum are not identical.

## Suggested CLI

As built (matches the other tools' `<lat,long> [year] [month]` arguments; no date means today):

```
tides.py <lat,long> [year] [month] [day] [--units ft|m] [--tz ZONE] [--station ID] [--refresh] [--no-color]
```

Example output:

```
Station: PORTLAND, ME (NOAA 8418150) — 2.3 mi from 43.6400, -70.2200
Heights in ft above MLLW, times America/New_York

Date        Time    Tide   Height
Sat Sep 19  05:56   High     7.6
Sat Sep 19  11:44   Low      2.3
Sat Sep 19  18:05   High     8.5
```

Implementation notes for Python:

- The stdlib is enough for HTTP and JSON (`urllib.request`, `json`), distance (`math`), and time zones (`zoneinfo`, Python 3.9+). `requests` is a convenience, `timezonefinder` is the only dependency that adds real capability.
- Haversine over ~4,600 stations is instant; no spatial index needed.
- Show the distance to the chosen station and warn when it is large (e.g. over 50 miles / 80 km), since the nearest station may then be a poor match. Straight-line nearest can also pick a station across a peninsula or up a river; a `--station` override is a cheap escape hatch.
- Cache station lists under something like `~/.cache/tides/` as JSON with a fetch timestamp.
- Set a request timeout and a descriptive `User-Agent`.

## Test points

| Location              | Lat, Lon            | Expected station            |
| --------------------- | ------------------- | --------------------------- |
| Portland, ME          | 43.6591, -70.2568   | NOAA 8418150 PORTLAND       |
| Bar Harbor, ME        | 44.3876, -68.2039   | NOAA 8413320 BAR HARBOR     |
| St. John's, NL        | 47.5615, -52.7126   | CHS 00905 St. Johns         |
