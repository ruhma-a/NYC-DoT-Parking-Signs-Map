import pandas as pd

# Load dataset
file_path = r"C:\Users\arsha\Downloads\Parking_Regulation_Locations_and_Signs_20261016.csv"
df = pd.read_csv(file_path)

# Identify coordinate columns 
lat_col = 'sign_y_coord'
lon_col = 'sign_x_coord'

# Filter out rows missing latitude or longitude
cleaned_df = df.dropna(subset=[lat_col, lon_col])

# Filter for current signs (practical so we only have signs that still exist)
if 'record_type' in cleaned_df.columns:
    cleaned_df = cleaned_df[cleaned_df['record_type'] == 'Current']

# Export the clean data to use for geospatial mapping
output_path = 'Cleaned_Parking_Data.csv'
cleaned_df.to_csv(output_path, index=False)

print(f"Data cleaned!! Original rows: {len(df)} | Cleaned rows: {len(cleaned_df)}")