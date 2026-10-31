import argparse
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString
from shapely.ops import linemerge, substring
from shapely.strtree import STRtree

NYC_STATE_PLANE = "EPSG:2263"
BOROUGH_CODES = {"Manhattan": 1, "Bronx": 2, "Brooklyn": 3, "Queens": 4, "Staten Island": 5}
SIDE_VECTORS = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
COMPASS_VECTORS = {"North": (0, 1), "South": (0, -1), "East": (1, 0), "West": (-1, 0)}

MAX_MATCH_DISTANCE_FT = 100
DEFAULT_STREET_WIDTH_FT = 30
MIN_ZONE_LENGTH_FT = 1

# Strictest first; the first pattern found in a description sets the zone's rule class
RULE_CLASSES = [
    ("no_stopping", r"NO STOPPING"),
    ("no_standing", r"NO STANDING"),
    ("no_parking", r"NO PARKING"),
    ("loading", r"LOADING|TRUCK|TAXI|BUS STOP|BUS LAYOVER"),
    ("limited_parking", r"HMP|METER|\bPARKING\b|\d\s*HR"),
]
NOISE_PATTERN = re.compile(r"PANEL|LOCATOR NUMBER")


def normalize_name(name):
    return " ".join(str(name).upper().split())


def load_signs(csv_path):
    df = pd.read_csv(csv_path, low_memory=False)
    total = len(df)

    # Only signs with coordinates can be placed on the map
    df = df.dropna(subset=["sign_x_coord", "sign_y_coord"]).copy()
    if "record_type" in df.columns:
        df = df[df["record_type"] == "Current"].copy()
    print(f"Signs with coordinates: {len(df):,} of {total:,}")

    df["street_key"] = df["on_street"].map(normalize_name)
    df["boro_code"] = df["borough"].map(BOROUGH_CODES)

    desc = df["sign_description"].fillna("")
    df["regulation"] = (
        desc.str.replace(r"\(SUPERSEDES[^)]*\)?", "", regex=True)
        .str.replace(r"\s*(<-+>|<-+|-+>)\s*", " ", regex=True)
        .str.split().str.join(" ")
    )
    arrow = desc.str.extract(r"(<-+>|<-+|-+>)")[0]
    df["arrow"] = np.where(
        arrow.isna(), "both",
        np.where(arrow.str.startswith("<") & arrow.str.endswith(">"), "both", "one_way"),
    )
    df = df[~desc.str.contains(NOISE_PATTERN)]
    return df


def load_lion(gdb_path, layer):
    lion = gpd.read_file(gdb_path, layer=layer)
    lion = lion.to_crs(NYC_STATE_PLANE)
    # FeatureTyp '0' is a real street; other values are rail, shoreline, bridges, etc.
    lion = lion[lion["FeatureTyp"] == "0"].copy()
    lion["street_key"] = lion["Street"].map(normalize_name)
    lion["geometry"] = lion.geometry.map(
        lambda g: linemerge(g) if g.geom_type == "MultiLineString" else g
    )
    lion = lion[lion.geometry.geom_type == "LineString"]
    return lion.reset_index(drop=True)


def match_signs_to_lion(signs, lion):
    # Match on street name and borough first, then take the nearest of those segments
    locations = signs.drop_duplicates(["boro_code", "street_key", "sign_x_coord", "sign_y_coord"])
    locations = locations[["boro_code", "street_key", "sign_x_coord", "sign_y_coord"]].copy()
    locations["lion_idx"] = -1
    locations["match_dist"] = np.inf

    lion_by_key = {}
    for boro in BOROUGH_CODES.values():
        in_boro = lion[(lion["LBoro"] == boro) | (lion["RBoro"] == boro)]
        for key, group in in_boro.groupby("street_key"):
            lion_by_key[(boro, key)] = group

    for key, group in locations.groupby(["boro_code", "street_key"]):
        candidates = lion_by_key.get(key)
        if candidates is None:
            continue
        points = shapely.points(group["sign_x_coord"].values, group["sign_y_coord"].values)
        tree = STRtree(candidates.geometry.values)
        point_idx, line_idx = tree.query_nearest(points, return_distance=False, all_matches=False)
        dist = shapely.distance(points[point_idx], candidates.geometry.values[line_idx])
        locations.loc[group.index[point_idx], "lion_idx"] = candidates.index.values[line_idx]
        locations.loc[group.index[point_idx], "match_dist"] = dist

    matched = signs.merge(
        locations, on=["boro_code", "street_key", "sign_x_coord", "sign_y_coord"], how="left"
    )
    matched["reject_reason"] = np.where(
        matched["lion_idx"] < 0, "no_lion_street_name_match",
        np.where(matched["match_dist"] > MAX_MATCH_DISTANCE_FT, "too_far_from_lion_segment", ""),
    )
    return matched


def curb_line(centerline, side):
    # The curb is the centerline offset half the street width toward the sign's side.
    # Shapely offsets to the left for positive distances, so pick the sign from the left normal.
    x0, y0 = centerline.coords[0]
    x1, y1 = centerline.coords[-1]
    dx, dy = x1 - x0, y1 - y0
    length = np.hypot(dx, dy)
    if length == 0:
        return None
    left_normal = (-dy / length, dx / length)
    sx, sy = SIDE_VECTORS[side]
    alignment = left_normal[0] * sx + left_normal[1] * sy
    if abs(alignment) < 0.2:
        return None
    return alignment > 0


def tangent_at(centerline, position_ft):
    a = centerline.interpolate(max(position_ft - 5, 0))
    b = centerline.interpolate(min(position_ft + 5, centerline.length))
    return b.x - a.x, b.y - a.y


def classify(text):
    for name, pattern in RULE_CLASSES:
        if re.search(pattern, text):
            return name
    return "other"


def strictest_class(texts):
    classes = [classify(t) for t in texts]
    for name, _ in RULE_CLASSES:
        if name in classes:
            return name
    return "other"


def build_zones(group, centerline, width_ft, side):
    """Cut the curb for one segment side into pieces, each carrying the signs that govern it."""
    offset_left = curb_line(centerline, side)
    if offset_left is None:
        return None, "side_does_not_fit_segment_direction"

    distance = (width_ft / 2) * (1 if offset_left else -1)
    curb = shapely.offset_curve(centerline, distance)
    if curb.geom_type == "MultiLineString":
        curb = linemerge(curb)
    if curb.geom_type != "LineString" or curb.length == 0:
        return None, "curb_offset_failed"

    seg_len = centerline.length
    group = group.copy()
    group["position"] = shapely.line_locate_point(
        centerline, shapely.points(group["sign_x_coord"].values, group["sign_y_coord"].values)
    )
    stops = sorted(group["position"].round(1).unique())
    bounds = [0.0] + stops + [seg_len]

    # Each sign governs the curb up to its neighbouring signs, or the end of the block
    spans = []
    for _, sign in group.iterrows():
        pos = round(sign["position"], 1)
        i = stops.index(pos) + 1
        prev_stop, next_stop = bounds[i - 1], bounds[i + 1]
        direction = "both"
        if sign["arrow"] == "one_way" and sign["arrow_direction"] in COMPASS_VECTORS:
            tx, ty = tangent_at(centerline, pos)
            cx, cy = COMPASS_VECTORS[sign["arrow_direction"]]
            direction = "forward" if tx * cx + ty * cy > 0 else "backward"
        start = pos if direction == "forward" else prev_stop
        end = pos if direction == "backward" else next_stop
        spans.append((start, end, sign))

    cuts = sorted({b for s, e, _ in spans for b in (s, e)})
    zones = []
    for start, end in zip(cuts[:-1], cuts[1:]):
        if end - start < MIN_ZONE_LENGTH_FT:
            continue
        signs = [sign for s, e, sign in spans if s <= start and e >= end]
        if not signs:
            continue
        texts = list(dict.fromkeys(s["regulation"] for s in signs))
        geom = substring(curb, start / seg_len, end / seg_len, normalized=True)
        if geom.geom_type != "LineString" or geom.is_empty:
            continue
        first = signs[0]
        zones.append({
            "SegmentID": first["SegmentID"],
            "on_street": first["on_street"],
            "from_street": first["from_street"],
            "to_street": first["to_street"],
            "borough": first["borough"],
            "side_of_street": side,
            "start_ft": round(start, 1),
            "end_ft": round(end, 1),
            "rule_class": strictest_class(texts),
            "regulations": " | ".join(texts),
            "order_numbers": ", ".join(dict.fromkeys(s["order_number"] for s in signs)),
            "geometry": geom,
        })
    return zones, ""


def main():
    parser = argparse.ArgumentParser(description="Map parking regulations onto LION curb lines")
    parser.add_argument("--signs", default="data/Parking_Regulation_Locations_and_Signs_20261030.csv")
    parser.add_argument("--lion", default="data/lion/lion.gdb")
    parser.add_argument("--lion-layer", default="lion")
    parser.add_argument("--out", default="continuous_parking_zones.geojson")
    parser.add_argument("--rejects", default="rejected_signs.csv")
    args = parser.parse_args()

    signs = load_signs(args.signs)
    lion = load_lion(args.lion, args.lion_layer)
    print(f"LION street segments: {len(lion):,}")

    print("Matching parking signs to LION segments...")
    matched = match_signs_to_lion(signs, lion)
    rejected = matched[matched["reject_reason"] != ""].copy()
    good = matched[matched["reject_reason"] == ""].copy()
    good["lion_idx"] = good["lion_idx"].astype(int)
    good = good.merge(
        lion[["SegmentID", "StreetWidth_Min"]], left_on="lion_idx", right_index=True, how="left"
    )

    print("Cutting curb lines into regulated zones...")
    zones = []
    reasons = []
    for (lion_idx, side), group in good.groupby(["lion_idx", "side_of_street"]):
        width = group["StreetWidth_Min"].iloc[0]
        if pd.isna(width) or width < 10:
            width = DEFAULT_STREET_WIDTH_FT
        result, reason = build_zones(group, lion.geometry[lion_idx], width, side)
        if result is None:
            group = group.assign(reject_reason=reason)
            reasons.append(group)
        else:
            zones.extend(result)

    if reasons:
        rejected = pd.concat([rejected] + reasons)

    gdf = gpd.GeoDataFrame(zones, geometry="geometry", crs=NYC_STATE_PLANE).to_crs("EPSG:4326")
    gdf.to_file(args.out, driver="GeoJSON")
    rejected.drop(columns=["lion_idx"], errors="ignore").to_csv(args.rejects, index=False)

    print(f"Sign records used: {len(signs) - len(rejected):,} | rejected: {len(rejected):,}")
    print(rejected["reject_reason"].value_counts().to_string())
    print(f"Success! {len(gdf):,} curb zones saved to {args.out}.")


if __name__ == "__main__":
    main()
