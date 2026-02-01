Let's create a new script called darknights.py.
It will use the following URL to get yearly tables:
https://aa.usno.navy.mil/data/RS_OneYear

DO NOT use the API, use the link above and use the table creation form to get the data.
The Type of Table field will have the needed types of data.

Fetch the tables for sunrise/sunset, moonrise/moonset, and astronomical twilight

Use variables for these configuration settings:
* Use UTC -4 for EDT timezone.
* Use GPS coords 44.81, -66.95
* Use 2026 for the year.

For the month of June print each day with the following:
* Sunset time
* End time of astronomical twilight
* State of the moon at the end of astronomical twilight, meaning:
  * Up - moon is above the horizon
  * Down - moon is below the horizon
* Display the moon set or moon rise time after sunset following these rules:
  * If state of the moon at sunset is Up, then
    * Display the time of the moonset that night even if it is the next day.
  * If the state of the moon at sunset is Down, then
    * Display the time of the moonrise that night even if it is the next day.
  * If it is the next day indicate that with (next day) text.
* Display the start of astronomical twilight for the next morning.
