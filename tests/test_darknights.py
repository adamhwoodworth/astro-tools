import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from darknights import date_range, parse_cli

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CACHE_DIR = Path("cache")
LATLONG = "44.81,-66.95"


def run_darknights(*args):
    """Run darknights.py with given arguments."""
    result = subprocess.run(
        ["uv", "run", "darknights.py", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result


def extract_table(output):
    """Extract the astronomical data table from output (month title through last row)."""
    lines = output.split("\n")
    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    table_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if any(stripped.startswith(m) for m in month_names):
            table_start = i
            break
    if table_start is None:
        return ""
    # Trim trailing blank lines
    table_lines = lines[table_start:]
    while table_lines and not table_lines[-1].strip():
        table_lines.pop()
    return "\n".join(table_lines)


@pytest.fixture(scope="session", autouse=True)
def cleanup_cache():
    """Remove all cache files before any tests run."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    yield


def test_no_cache_downloads_without_saving():
    """--no-cache downloads fresh data, does not save, does not create cache dir."""
    result = run_darknights(LATLONG, "2026", "jun", "--no-color", "--no-cache")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert result.stdout.count("Downloading from USNO...") == 3
    assert result.stdout.count("Saved to cache") == 0
    assert result.stdout.count("Using cached data") == 0
    assert not CACHE_DIR.exists(), "Cache directory should not be created with --no-cache"

    expected = (FIXTURES_DIR / "expected_table_2026_jun.txt").read_text().rstrip("\n")
    assert extract_table(result.stdout) == expected


def test_first_run_downloads_and_caches():
    """First run without --no-cache downloads all 3 tables and saves each to cache."""
    result = run_darknights(LATLONG, "2026", "jun", "--no-color")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert result.stdout.count("Downloading from USNO...") == 3
    assert result.stdout.count("Saved to cache") == 3
    assert result.stdout.count("Using cached data") == 0

    assert CACHE_DIR.exists(), "Cache directory should exist"
    assert len(list(CACHE_DIR.glob("*.html"))) == 3, "Should have 3 cache files"

    expected = (FIXTURES_DIR / "expected_table_2026_jun.txt").read_text().rstrip("\n")
    assert extract_table(result.stdout) == expected


def test_second_run_uses_cache():
    """Second run reads all 3 tables from cache, no downloads."""
    result = run_darknights(LATLONG, "2026", "jun", "--no-color")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert result.stdout.count("Using cached data") == 3
    assert result.stdout.count("Downloading from USNO") == 0
    assert result.stdout.count("Saved to cache") == 0

    expected = (FIXTURES_DIR / "expected_table_2026_jun.txt").read_text().rstrip("\n")
    assert extract_table(result.stdout) == expected


def test_no_cache_bypasses_existing_cache():
    """--no-cache bypasses existing cache without deleting it."""
    cache_files_before = sorted(CACHE_DIR.glob("*.html"))
    mtimes_before = {f: f.stat().st_mtime for f in cache_files_before}

    result = run_darknights(LATLONG, "2026", "jun", "--no-color", "--no-cache")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert result.stdout.count("Downloading from USNO...") == 3
    assert result.stdout.count("Using cached data") == 0
    assert result.stdout.count("Saved to cache") == 0

    # Cache files should still exist, unmodified
    cache_files_after = sorted(CACHE_DIR.glob("*.html"))
    assert cache_files_after == cache_files_before
    for f in cache_files_after:
        assert f.stat().st_mtime == mtimes_before[f], f"Cache file {f.name} was modified"

    expected = (FIXTURES_DIR / "expected_table_2026_jun.txt").read_text().rstrip("\n")
    assert extract_table(result.stdout) == expected


# --- Date arguments ------------------------------------------------------------

TODAY = date(2026, 10, 7)


def test_no_date_shows_the_whole_current_year():
    assert date_range(parse_cli([LATLONG]), TODAY) == (date(2026, 1, 1), date(2026, 12, 31))


def test_days_without_a_date_start_today():
    assert date_range(parse_cli([LATLONG, "+3"]), TODAY) == (TODAY, date(2026, 10, 9))


def test_day_and_days_narrow_the_range():
    args = parse_cli([LATLONG, "2028", "jun", "8", "+12", "--no-cache"])
    assert date_range(args, TODAY) == (date(2028, 6, 8), date(2028, 6, 19))
    assert args.no_cache


def test_day_range_shows_only_those_nights():
    result = run_darknights(LATLONG, "2026", "jun", "29", "+3", "--no-color")
    assert result.returncode == 0, f"stderr: {result.stderr}"

    dates = [line[:10] for line in result.stdout.splitlines() if line[:3] in ("Mon", "Tue", "Wed", "Thu")]
    assert dates == ["Mon Jun 29", "Tue Jun 30", "Wed Jul  1"]
    assert "June 2026" in result.stdout and "July 2026" in result.stdout


def test_day_that_does_not_exist_is_an_error():
    result = run_darknights(LATLONG, "2026", "feb", "30", "--no-color")
    assert result.returncode == 1
    assert "Error" in result.stderr
