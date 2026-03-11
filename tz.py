import sys
from timezonefinder import TimezoneFinder
from zoneinfo import ZoneInfo
from datetime import datetime


if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} 'lat, long'", file=sys.stderr)
    print("  Example: uv run tz.py '44.82611003049705, -66.93291767410354'", file=sys.stderr)
    sys.exit(1)

parts = sys.argv[1].split(",")
if len(parts) != 2:
    print("Error: expected 'lat, long' format", file=sys.stderr)
    sys.exit(1)

lat = float(parts[0].strip())
lng = float(parts[1].strip())

tf = TimezoneFinder()
tz_name = tf.timezone_at(lat=lat, lng=lng)

dt = datetime(2026, 6, 15, tzinfo=ZoneInfo(tz_name))
offset_hours = dt.utcoffset().total_seconds() / 3600

print(f"Location: {lat}, {lng}")
print(f"Timezone: {tz_name}")
print(f"UTC offset: {offset_hours:+.1f}")
