import argparse
import json
import os

import geopandas as gpd

KEEP_COLUMNS = [
    "SegmentID", "on_street", "from_street", "to_street",
    "side_of_street", "rule_class", "regulations", "geometry",
]
COORDINATE_DECIMALS = 6


def main():
    parser = argparse.ArgumentParser(description="Split the curb zones into one slim GeoJSON per borough")
    parser.add_argument("--zones", default="continuous_parking_zones.geojson")
    parser.add_argument("--out-dir", default="zones")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    gdf = gpd.read_file(args.zones)

    for borough, part in gdf.groupby("borough"):
        path = os.path.join(args.out_dir, f"zones_{borough.lower().replace(' ', '_')}.geojson")
        part[KEEP_COLUMNS].to_file(path, driver="GeoJSON", COORDINATE_PRECISION=COORDINATE_DECIMALS)

        # GDAL pretty-prints; rewrite compactly so each file stays well under GitHub's size limits
        with open(path) as f:
            features = json.load(f)["features"]
        with open(path, "w") as f:
            json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"), ensure_ascii=False)
        print(f"{path}: {len(part):,} zones, {os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
