import requests
import geopandas as gpd
import pandas as pd
import zipfile
import io
import datetime
from shapely.geometry import box

OOKLA_URL = "https://github.com/teamookla/ookla-open-data/raw/master/mobile/"

def find_latest_quarter():
    now = datetime.datetime.utcnow()
    q = (now.month - 1) // 3 + 1
    return f"{now.year}_Q{q}"

def download_latest_parquet():
    quarter = find_latest_quarter()
    filename = f"{quarter}_mobile_tiles.parquet"
    url = f"{OOKLA_URL}{filename}"

    print(f"Downloading {url}...")
    r = requests.get(url)

    if r.status_code != 200:
        raise RuntimeError(f"Failed to download {url}")

    open("latest.parquet", "wb").write(r.content)
    print("Downloaded latest.parquet")

def filter_johor():
    print("Loading parquet...")
    df = pd.read_parquet("latest.parquet")

    print("Converting geometry...")
    gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df["tile"]))

    johor_bbox = box(
        103.28, 1.2,   # min lon, min lat
        104.6, 2.7     # max lon, max lat
    )

    print("Filtering Johor...")
    gdf = gdf[gdf.intersects(johor_bbox)]
    gdf.to_file("johor.geojson", driver="GeoJSON")
    print("Saved johor.geojson")

if __name__ == "__main__":
    download_latest_parquet()
    filter_johor()
