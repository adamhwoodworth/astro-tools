# Astro Tools Project

See README.md for usage and examples.

## Layout

- The four scripts at the repo root (`darknights.py`, `fullmoon.py`, `tides.py`, `nightplan.py`) only parse arguments, call the library, and print
- Shared code lives in the `astro_tools` package under `src/astro_tools/` (src layout, `uv_build` backend): `common.py` (CLI, dates, colored tables, USNO fetch), `nights.py`, `tides.py`
- Scripts never import from each other; code needed by two scripts goes in `astro_tools`
- `uv sync` / `uv run` install the package into `.venv` in editable mode, so `import astro_tools` works without path tweaks

## Dev Notes

- Always use `uv run` to run scripts and tests
- Run tests: `uv run pytest -v`
- Lint: `uv run ruff check` (rules `E`, `F`, `I`); auto-fix with `uv run ruff check --fix`
- Format: `uv run ruff format` (double quotes, 120-col line length)
- `.githooks/pre-commit` auto-formats staged Python files and blocks commits with lint errors; enable per clone with `git config core.hooksPath .githooks`
- Timezone is auto-detected from coordinates using `timezonefinder`
- USNO API results are cached in `cache/` (MD5 hash of request parameters)
- `tides.py` caches the merged NOAA/CHS station list in `cache/tides_stations.json` (30-day expiry, `--refresh` to force); tide predictions are never cached
- `docs/superpowers/specs/2026-09-19-tides-script-design.md` holds the verified NOAA/CHS API notes behind `tides.py`
- `nightplan.py` combines `tides.py` and `darknights.py`
