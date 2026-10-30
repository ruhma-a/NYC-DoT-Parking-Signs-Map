# Curb-line mapping: summary

`map_curb_lines.py` attaches NYC DOT parking regulations to LION street geometry and writes `continuous_parking_zones.geojson`.

## Inputs
- **Parking Regulation Locations and Signs** CSV (OpenData). Only signs with `sign_x_coord`/`sign_y_coord` are used. These are NYC State Plane feet (EPSG:2263), not lat/lon.
- **LION** (`lion.gdb`, layer `lion`, same CRS). Street-type segments only (`FeatureTyp == '0'`).

## How continuous zones are built
1. **Match:** each sign is matched to the nearest LION segment with the same street name and borough (within 100 ft).
2. **Curb:** the segment centerline is offset half of `StreetWidth_Min` toward the sign's `side_of_street`.
3. **Position:** each sign is projected onto the segment to get its distance along the block, so signs are ordered by position and not by CSV row.
4. **Extent:** a sign governs the curb up to its neighbouring signs or the end of the segment. A one-way arrow (`arrow_direction`) limits it to one direction. A two-way arrow, or none, covers both.
5. **Cut:** the curb is cut at every boundary. Each piece lists all the regulations covering it and gets a `rule_class` (the strictest rule wins).

## Output
Each zone has `SegmentID`, `on_street`, `from_street`, `to_street`, `borough`, `side_of_street`, `start_ft`, `end_ft`, `rule_class`, `regulations` and `order_numbers`. The file is in EPSG:4326. Signs that can't be placed go to `rejected_signs.csv` with a reason.

## Run
```
python map_curb_lines.py --signs <parking csv> --lion <lion.gdb>
```

## First run (CSV dated 2026-10-30)
- 403,859 of 440,868 signs have coordinates.
- 308,769 curb zones were produced and about 10,000 sign records rejected.
- The main reject reason is street-name aliases such as "6 AVENUE" and "THIRD AVENUE". LION's alternate-names table could resolve these.
- Spot check: 3 Avenue between E 85 and E 86 St, west side, gives 284.7 ft of curb in zones that match the sign positions.

## Not done yet
- Parsing days and hours (for the time-of-day filter).
- The map viewer.
