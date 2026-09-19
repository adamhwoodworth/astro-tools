"""Tests for tides.py.

Unit tests cover the pure station-matching, parsing, labelling, and date logic
using records trimmed from real NOAA and CHS responses. Integration tests run
the script against the live APIs for the verified test points.
"""

import subprocess
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from tides import (
    Station,
    TideError,
    TideEvent,
    build_rows,
    cache_is_fresh,
    date_chunks,
    events_in_window,
    find_station,
    get_json,
    haversine_miles,
    header_lines,
    label_hilo,
    local_window,
    nearest_station,
    normalise_chs_stations,
    normalise_noaa_stations,
    parse_chs_predictions,
    parse_cli,
    parse_noaa_predictions,
    resolve_date_range,
)

NOAA_STATIONS_JSON = {
    "count": 2,
    "stations": [
        {"id": "8413320", "name": "BAR HARBOR", "state": "ME", "lat": 44.39219444444444, "lng": -68.20427777777778},
        {"id": "8418150", "name": "PORTLAND", "state": "ME", "lat": 43.65805555555556, "lng": -70.24416666666667},
        {"id": "1619910", "name": "SAND ISLAND, MIDWAY ISLANDS", "state": "", "lat": 28.2117, "lng": -177.36},
    ],
}

CHS_STATIONS_JSON = [
    {
        "id": "5cebf1e33d0f4a073c4bc176",
        "code": "00905",
        "officialName": "St. Johns",
        "latitude": 47.567045,
        "longitude": -52.702311,
        "timeSeries": [{"code": "wlo"}, {"code": "wlp"}, {"code": "wlp-hilo"}],
    },
    {
        # Closer to Petty Harbour than St. Johns is, but has no predictions.
        "id": "5dd3064de0fdc4b9b4be6697",
        "code": "00903",
        "officialName": "Petty Harbour",
        "latitude": 47.466667,
        "longitude": -52.7,
        "timeSeries": [],
    },
]

PORTLAND = Station("NOAA", "8418150", "8418150", "PORTLAND, ME", 43.65805555555556, -70.24416666666667)
BAR_HARBOR = Station("NOAA", "8413320", "8413320", "BAR HARBOR, ME", 44.39219444444444, -68.20427777777778)
ST_JOHNS = Station("CHS", "5cebf1e33d0f4a073c4bc176", "00905", "St. Johns", 47.567045, -52.702311)


# --- haversine_miles ---------------------------------------------------------


def test_haversine_one_degree_of_latitude_is_about_69_miles():
    assert haversine_miles(44.0, -68.0, 45.0, -68.0) == pytest.approx(69.09, abs=0.05)


def test_haversine_same_point_is_zero():
    assert haversine_miles(43.6591, -70.2568, 43.6591, -70.2568) == 0


def test_haversine_portland_to_bar_harbor():
    # ~113 statute miles by any great-circle calculator.
    assert haversine_miles(43.6591, -70.2568, 44.3876, -68.2039) == pytest.approx(113.4, abs=0.5)


# --- station normalisation ---------------------------------------------------


def test_noaa_stations_are_normalised_with_state_in_name():
    stations = normalise_noaa_stations(NOAA_STATIONS_JSON)
    assert stations[:2] == [BAR_HARBOR, PORTLAND]


def test_noaa_station_without_state_keeps_bare_name():
    stations = normalise_noaa_stations(NOAA_STATIONS_JSON)
    assert stations[2].name == "SAND ISLAND, MIDWAY ISLANDS"


def test_chs_stations_without_hilo_predictions_are_dropped():
    assert normalise_chs_stations(CHS_STATIONS_JSON) == [ST_JOHNS]


# --- nearest_station ---------------------------------------------------------


def test_nearest_station_picks_closest_across_both_sources():
    stations = [PORTLAND, BAR_HARBOR, ST_JOHNS]
    station, miles = nearest_station(47.5615, -52.7126, stations)
    assert station == ST_JOHNS
    assert miles == pytest.approx(0.6, abs=0.1)


def test_nearest_station_for_bar_harbor_point():
    station, _ = nearest_station(44.3876, -68.2039, [PORTLAND, BAR_HARBOR, ST_JOHNS])
    assert station == BAR_HARBOR


# --- label_hilo --------------------------------------------------------------


def test_label_hilo_alternates_from_a_low_start():
    assert label_hilo([0.945, 0.704, 1.165, 0.764]) == ["High", "Low", "High", "Low"]


def test_label_hilo_last_event_uses_previous_neighbour():
    # The last value has no following neighbour; 1.4 > 0.3 so it is a High.
    assert label_hilo([1.2, 0.3, 1.4]) == ["High", "Low", "High"]


def test_label_hilo_higher_low_is_still_a_low():
    # Mixed tides: a "higher low" (0.9) sits well above the day's other low
    # (0.2). Each event is judged against its neighbour, not a fixed level.
    assert label_hilo([0.2, 1.0, 0.9, 1.6]) == ["Low", "High", "Low", "High"]


def test_label_hilo_single_event_cannot_be_inferred():
    assert label_hilo([1.0]) == ["?"]


# --- prediction parsing ------------------------------------------------------


def test_noaa_predictions_parse_gmt_times_string_heights_and_types():
    data = {
        "predictions": [
            {"t": "2026-09-19 03:38", "v": "0.451", "type": "L"},
            {"t": "2026-09-19 09:56", "v": "2.314", "type": "H"},
        ]
    }
    assert parse_noaa_predictions(data) == [
        TideEvent(datetime(2026, 9, 19, 3, 38, tzinfo=UTC), "Low", 0.451),
        TideEvent(datetime(2026, 9, 19, 9, 56, tzinfo=UTC), "High", 2.314),
    ]


def test_noaa_error_body_raises_with_the_api_message():
    data = {"error": {"message": " The station is not a valid station or there is system error."}}
    with pytest.raises(TideError, match="not a valid station"):
        parse_noaa_predictions(data)


def test_chs_predictions_are_labelled_from_neighbours():
    data = [
        {"eventDate": "2026-09-19T02:52:00Z", "qcFlagCode": "1", "value": 0.945},
        {"eventDate": "2026-09-19T08:29:00Z", "qcFlagCode": "1", "value": 0.704},
        {"eventDate": "2026-09-19T15:41:00Z", "qcFlagCode": "1", "value": 1.165},
    ]
    assert parse_chs_predictions(data) == [
        TideEvent(datetime(2026, 9, 19, 2, 52, tzinfo=UTC), "High", 0.945),
        TideEvent(datetime(2026, 9, 19, 8, 29, tzinfo=UTC), "Low", 0.704),
        TideEvent(datetime(2026, 9, 19, 15, 41, tzinfo=UTC), "High", 1.165),
    ]


def test_chs_event_repeated_at_a_chunk_boundary_is_kept_once():
    data = [
        {"eventDate": "2026-09-19T08:29:00Z", "value": 0.704},
        {"eventDate": "2026-09-19T02:52:00Z", "value": 0.945},
        {"eventDate": "2026-09-19T08:29:00Z", "value": 0.704},
    ]
    assert [e.kind for e in parse_chs_predictions(data)] == ["High", "Low"]


# --- resolve_date_range ------------------------------------------------------

TODAY = date(2026, 9, 19)


def test_no_date_arguments_means_today():
    assert resolve_date_range(None, None, None, TODAY) == (TODAY, TODAY)


def test_year_only_covers_the_whole_year():
    assert resolve_date_range(2027, None, None, TODAY) == (date(2027, 1, 1), date(2027, 12, 31))


def test_year_and_month_cover_the_whole_month():
    assert resolve_date_range(2028, 2, None, TODAY) == (date(2028, 2, 1), date(2028, 2, 29))


def test_year_month_day_is_a_single_day():
    assert resolve_date_range(2026, 10, 4, TODAY) == (date(2026, 10, 4), date(2026, 10, 4))


def test_day_that_does_not_exist_in_the_month_is_rejected():
    with pytest.raises(ValueError):
        resolve_date_range(2026, 2, 30, TODAY)


# --- local_window / events_in_window ----------------------------------------


def test_local_window_spans_local_midnights_in_utc():
    # Newfoundland daylight time is UTC-2:30.
    start, end = local_window(date(2026, 9, 19), date(2026, 9, 19), ZoneInfo("America/St_Johns"))
    assert start == datetime(2026, 9, 19, 2, 30, tzinfo=UTC)
    assert end == datetime(2026, 9, 20, 2, 30, tzinfo=UTC)


def test_local_window_on_fall_back_day_is_25_hours():
    start, end = local_window(date(2026, 11, 1), date(2026, 11, 1), ZoneInfo("America/New_York"))
    assert (end - start).total_seconds() == 25 * 3600


def test_events_in_window_is_half_open():
    start = datetime(2026, 9, 19, 4, tzinfo=UTC)
    end = datetime(2026, 9, 20, 4, tzinfo=UTC)
    before = TideEvent(datetime(2026, 9, 19, 3, 59, tzinfo=UTC), "Low", 0.1)
    at_start = TideEvent(start, "High", 2.0)
    at_end = TideEvent(end, "Low", 0.2)
    assert events_in_window([before, at_start, at_end], start, end) == [at_start]


# --- date_chunks -------------------------------------------------------------


def test_short_span_is_a_single_chunk():
    start = datetime(2026, 9, 18, tzinfo=UTC)
    end = datetime(2026, 9, 21, tzinfo=UTC)
    assert date_chunks(start, end, 180) == [(start, end)]


def test_long_span_is_split_into_contiguous_chunks_within_the_limit():
    start = datetime(2027, 12, 31, tzinfo=UTC)
    end = datetime(2029, 1, 1, tzinfo=UTC)  # 367 days: over the CHS 366-day limit
    assert date_chunks(start, end, 180) == [
        (start, datetime(2028, 6, 28, tzinfo=UTC)),
        (datetime(2028, 6, 28, tzinfo=UTC), datetime(2028, 12, 25, tzinfo=UTC)),
        (datetime(2028, 12, 25, tzinfo=UTC), end),
    ]


# --- find_station (--station override) --------------------------------------


def test_find_station_matches_the_chs_five_digit_code():
    assert find_station("00905", [PORTLAND, ST_JOHNS]) == ST_JOHNS


def test_find_station_unknown_id_is_an_error():
    with pytest.raises(TideError, match="9999999"):
        find_station("9999999", [PORTLAND, ST_JOHNS])


# --- build_rows / header_lines ----------------------------------------------

PORTLAND_EVENTS = [
    TideEvent(datetime(2026, 9, 19, 9, 56, tzinfo=UTC), "High", 2.314),
    TideEvent(datetime(2026, 9, 19, 15, 44, tzinfo=UTC), "Low", 0.698),
]


def test_rows_show_local_time_and_feet():
    # 09:56 UTC is 05:56 EDT; 2.314 m is 7.59 ft, matching NOAA's own
    # lst_ldt/english response for the same event ("05:56", "7.593").
    rows = build_rows(PORTLAND_EVENTS, ZoneInfo("America/New_York"), "ft")
    assert rows == [
        ["Sat Sep 19", "05:56", "High", "7.6"],
        ["Sat Sep 19", "11:44", "Low", "2.3"],
    ]


def test_rows_in_metres_keep_two_decimals():
    rows = build_rows(PORTLAND_EVENTS, ZoneInfo("America/New_York"), "m")
    assert [row[3] for row in rows] == ["2.31", "0.70"]


def test_rows_use_the_local_date_not_the_utc_date():
    late = [TideEvent(datetime(2026, 9, 20, 2, 5, tzinfo=UTC), "High", 2.603)]
    assert build_rows(late, ZoneInfo("America/New_York"), "ft")[0][:2] == ["Sat Sep 19", "22:05"]


def test_header_names_station_distance_datum_and_zone():
    text = "\n".join(header_lines(PORTLAND, 2.34, 43.64, -70.22, "ft", "America/New_York"))
    assert "PORTLAND, ME (NOAA 8418150)" in text
    assert "2.3 mi from 43.6400, -70.2200" in text
    assert "ft above MLLW" in text
    assert "America/New_York" in text


def test_header_for_chs_uses_chart_datum_and_km_with_metres():
    text = "\n".join(header_lines(ST_JOHNS, 10.0, 47.5615, -52.7126, "m", "America/St_Johns"))
    assert "St. Johns (CHS 00905)" in text
    assert "16.1 km from" in text
    assert "m above chart datum" in text


def test_header_warns_when_station_is_over_50_miles_away():
    far = header_lines(PORTLAND, 50.1, 43.0, -71.2, "ft", "America/New_York")
    near = header_lines(PORTLAND, 49.9, 43.0, -71.2, "ft", "America/New_York")
    assert any("Warning" in line for line in far)
    assert not any("Warning" in line for line in near)


# --- parse_cli ---------------------------------------------------------------


def test_cli_with_only_coordinates_has_no_date_and_defaults_to_feet():
    args = parse_cli(["44.85, -66.98"])
    assert (args.lat, args.lon) == (44.85, -66.98)
    assert (args.year, args.month, args.day) == (None, None, None)
    assert args.units == "ft"


def test_cli_year_month_day_follow_the_coordinates():
    args = parse_cli(["44.85,-66.98", "2026", "oct", "4", "--units", "m"])
    assert (args.year, args.month, args.day) == (2026, 10, 4)
    assert args.units == "m"


def test_cli_accepts_southern_latitude_that_starts_with_a_minus():
    args = parse_cli(["--no-color", "-14.28,-170.69", "2026"])
    assert (args.lat, args.lon) == (-14.28, -170.69)
    assert args.year == 2026
    assert args.no_color is True


def test_cli_rejects_a_month_that_is_not_a_three_letter_abbreviation():
    with pytest.raises(SystemExit):
        parse_cli(["44.85,-66.98", "2026", "october"])


def test_cli_rejects_missing_coordinates():
    with pytest.raises(SystemExit):
        parse_cli(["2026", "oct"])


# --- cache_is_fresh ----------------------------------------------------------

NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)


def test_station_list_fetched_29_days_ago_is_fresh():
    assert cache_is_fresh("2026-08-21T12:00:00+00:00", NOW) is True


def test_station_list_fetched_31_days_ago_is_stale():
    assert cache_is_fresh("2026-08-19T12:00:00+00:00", NOW) is False


# --- get_json ----------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}

    def json(self):
        return self.payload


class FakeHttp:
    """Serves queued responses and records how long the caller slept."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.slept = []

    def get(self, url, params=None, headers=None, timeout=None):
        return self.responses.pop(0)

    def sleep(self, seconds):
        self.slept.append(seconds)


def test_get_json_returns_the_decoded_body():
    http = FakeHttp([FakeResponse(200, {"predictions": []})])
    assert get_json("https://example.test", {}, get=http.get, sleep=http.sleep) == {"predictions": []}


def test_get_json_waits_and_retries_once_when_rate_limited():
    http = FakeHttp([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, [1, 2])])
    assert get_json("https://example.test", {}, get=http.get, sleep=http.sleep) == [1, 2]
    assert http.slept == [7]


def test_get_json_gives_up_when_still_rate_limited():
    http = FakeHttp([FakeResponse(429), FakeResponse(429)])
    with pytest.raises(TideError, match="429"):
        get_json("https://example.test", {}, get=http.get, sleep=http.sleep)


def test_get_json_reports_http_errors():
    http = FakeHttp([FakeResponse(404)])
    with pytest.raises(TideError, match="404"):
        get_json("https://example.test", {}, get=http.get, sleep=http.sleep)


# --- integration: live APIs --------------------------------------------------


def run_tides(*args):
    """Run tides.py with given arguments."""
    return subprocess.run(
        ["uv", "run", "tides.py", *args, "--no-color"],
        capture_output=True,
        text=True,
        timeout=120,
    )


def table_rows(output):
    """Tide rows of the printed table (lines starting with a weekday), right-trimmed."""
    weekdays = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    return [line.rstrip() for line in output.split("\n") if line.startswith(weekdays)]


@pytest.mark.parametrize(
    ("latlong", "expected_station"),
    [
        ("43.6591,-70.2568", "PORTLAND, ME (NOAA 8418150)"),
        ("44.3876,-68.2039", "BAR HARBOR, ME (NOAA 8413320)"),
        ("47.5615,-52.7126", "St. Johns (CHS 00905)"),
    ],
)
def test_nearest_station_for_verified_test_points(latlong, expected_station):
    result = run_tides(latlong)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert expected_station in result.stdout


def test_single_day_prints_only_that_day():
    result = run_tides("43.6591,-70.2568", "2026", "oct", "4")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    rows = table_rows(result.stdout)
    assert 3 <= len(rows) <= 5
    assert all(row.startswith("Sun Oct 04") for row in rows)


def test_heights_are_right_aligned_so_negative_lows_line_up():
    # Bar Harbor has a -0.3 ft low on the evening of 2026-10-01.
    result = run_tides("44.3876,-68.2039", "2026", "oct", "1")
    rows = table_rows(result.stdout)
    assert len({len(row) for row in rows}) == 1
    assert any(row.endswith("-0.3") for row in rows)


def test_chs_leap_year_needs_more_than_one_request_and_has_no_gaps():
    # 2028 plus fetch padding exceeds the CHS 366-day request limit.
    result = run_tides("47.5615,-52.7126", "2028")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert len({row[:10] for row in table_rows(result.stdout)}) == 366


def test_station_override_is_used_instead_of_the_nearest():
    result = run_tides("43.6591,-70.2568", "--station", "8413320")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "BAR HARBOR, ME (NOAA 8413320)" in result.stdout


def test_nonexistent_day_exits_with_an_error():
    result = run_tides("43.6591,-70.2568", "2026", "feb", "30")
    assert result.returncode == 1
    assert "Error" in result.stderr


def test_unknown_time_zone_exits_with_an_error():
    result = run_tides("43.6591,-70.2568", "--tz", "America/Nowhere")
    assert result.returncode == 1
    assert "America/Nowhere" in result.stderr


def test_times_use_the_requested_location_zone_not_the_stations():
    # Lubec, ME (Eastern time) is nearest a CHS station on Campobello Island,
    # which keeps Atlantic time, an hour ahead.
    result = run_tides("44.81,-66.95")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "(CHS " in result.stdout
    assert "times America/New_York" in result.stdout
