# Astro Tools Project

See README.md for usage and examples.

## Dev Notes

- Always use `uv run` to run scripts and tests
- Run tests: `uv run python -m pytest tests/ -v`
- Timezone is auto-detected from coordinates using `timezonefinder`
- USNO API results are cached in `cache/` (MD5 hash of request parameters)
