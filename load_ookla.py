import requests
import pandas as pd
import pyarrow.parquet as pq
import os
import json
from shapely.geometry import Point, mapping

# Malaysia-only file (much smaller & guaranteed to exist)
OOKLA_FILE = "https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=mobile/year=2024/quarter=4/2024-10-01_performance_mobile_tiles.parquet"

OUT_DIR = "data"
OUT_FILE = "data/ookla_johor.geojson"

# Approx Johor bounding box (to reduce file size)
JH_MIN_LON = 103.0
JH_MAX_LON = 104.5
JH_MIN_LAT = 1.0
JH_MAX_LAT = 2.5

def download_parquet():
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = f"{OUT_DIR}/tiles.parquet"

    print("Downloading parquet...")
    r = requests.get(OOKLA_FILE, timeout=30)
    if r.status_code != 200:
        print("Failed to download parquet file.")
        return None

    with open(out_path, "wb") as f:
        f.write(r.content)

    print("Downloaded.")
    return out_path


def convert_to_geojson(parquet_file):
    print("Reading parquet...")

    table = pq.read_table(parquet_file)
    df = table.to_pandas()

    # Column names from Ookla schema
    if "tile_x" in df.columns and "tile_y" in df.columns:
        df["lon"] = df["tile_x"]
        df["lat"] = df["tile_y"]
    elif "longitude" in df.columns:
        df["lon"] = df["longitude"]
        df["lat"] = df["latitude"]
    else:
        raise ValueError("No coordinate columns found in parquet")

    print("Filtering Johor coordinates...")
    df = df[
        (df["lon"] >= JH_MIN_LON) &
        (df["lon"] <= JH_MAX_LON) &
        (df["lat"] >= JH_MIN_LAT) &
        (df["lat"] <= JH_MAX_LAT)
    ]

    print("Converting to GeoJSON...")
    features = []
    for _, row in df.iterrows():
        geom = Point(row["lon"], row["lat"])
        feat = {
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": {
                "download_mean": row.get("avg_d_kbps"),
                "upload_mean": row.get("avg_u_kbps"),
                "latency_mean": row.get("avg_lat_ms"),
                "provider": row.get("provider_name", "Unknown"),
            },
        }
        features.append(feat)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    with open(OUT_FILE, "w") as f:
        json.dump(geojson, f)

    print("GeoJSON saved:", OUT_FILE)


def main():
    parquet = download_parquet()
    if parquet is None:
        print("ERROR: download failed.")
        return

    convert_to_geojson(parquet)
    print("DONE.")


if __name__ == "__main__":
    main()
