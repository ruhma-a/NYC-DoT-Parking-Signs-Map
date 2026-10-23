import geopandas as gpd
from shapely.geometry import LineString
import pandas as pd

def main():
    points_file = 'path_to_parsed_points.csv'
    df_points = pd.read_csv(points_file)

    gdf_points = gpd.GeoDataFrame(
        df_points,
        geometry=gpd.points_from_xy(df_points.longitude, df_points.latitude),
        crs="EPSG:4326"
    )

    gdf_points = gdf_points.to_crs("EPSG:2263")

    curbs_file = 'nyc_curb_lines.geojson'
    gdf_curbs = gpd.read_file(curbs_file).to_crs("EPSG:2263")

    print("Snapping parking sign points to the nearest curb lines...")
    snapped_points = gpd.sjoin_nearest(
        gdf_points,
        gdf_curbs,
        how="left",
        distance_col="distance_to_curb"
    )

    def create_continuous_line(point_group):
        if len(point_group) > 1:
            return LineString(point_group.geometry.tolist())
        return None

    print("Generating continuous curb lines...")

    continuous_lines = snapped_points.groupby('segment_id').apply(create_continuous_line)

    gdf_continuous = gpd.GeoDataFrame(
        geometry=continuous_lines.dropna(),
        crs="EPSG:2263"
    )

    gdf_continuous.to_crs("EPSG:4326").to_file("continuous_parking_zones.geojson", driver="GeoJSON")
    print("Success! Continuous curb lines saved to continuous_parking_zones.geojson.")

if __name__ == "__main__":
    main()
