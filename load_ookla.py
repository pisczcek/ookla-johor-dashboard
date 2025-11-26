import pandas as pd
import pyarrow.parquet as pq
import requests
import os
import json
from shapely.geometry import Point, mapping

OOKLA_URL = "https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=fixed/year=2024/quarter=4/"

def download_parquet():
    files = [
        "2024-04-01_performance_fixed_tiles.parquet",
        "tiles.parquet"
    ]
    for name in files:
        url = OOKLA_URL + name
        out = f"data/{name}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                open(out, "wb").write(r.content)
                return out
        except:
            continue
    return None

def convert_to_geojson(parquet_file):
    table = pq.read_table(parquet_file)
    df = table.to_pandas()

    df["lon"] = df["tile_x"]
    df["lat"] = df["tile_y"]

    features = []
    for _, row in df.iterrows():
        geom = Point(row["lon"], row["lat"])
        feat = {
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": {
                "download_mean": row.get("avg_d_kbps", None),
                "upload_mean": row.get("avg_u_kbps", None),
                "latency_mean": row.get("avg_lat_ms", None),
                "provider": row.get("provider_name", "Unknown")
            }
        }
        features.append(feat)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    os.makedirs("data", exist_ok=True)
    with open("data/ookla_johor.geojson", "w") as f:
        json.dump(geojson, f)

def main():
    print("Downloading Ookla parquet...")
    parquet = download_parquet()
    if parquet is None:
        print("Failed to download any parquet file.")
        return

    print("Converting to GeoJSON...")
    convert_to_geojson(parquet)
    print("DONE – GeoJSON created.")

if __name__ == "__main__":
    main()
