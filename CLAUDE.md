# Astro Tools Project

See README.md for usage and examples.

## Dev Notes

- Always use `uv run` to run scripts and tests
- Run tests: `uv run python -m pytest tests/ -v`
- Lint: `uv run ruff check` (rules `E`, `F`, `I`); auto-fix with `uv run ruff check --fix`
- Format: `uv run ruff format` (double quotes, 120-col line length)
- Timezone is auto-detected from coordinates using `timezonefinder`
- USNO API results are cached in `cache/` (MD5 hash of request parameters)
- `tides.py` caches the merged NOAA/CHS station list in `cache/tides_stations.json` (30-day expiry, `--refresh` to force); tide predictions are never cached
- `docs/superpowers/specs/2026-09-19-tides-script-design.md` holds the verified NOAA/CHS API notes behind `tides.py`
