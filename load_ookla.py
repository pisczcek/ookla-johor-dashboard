import os
import requests
import pandas as pd
import math

os.makedirs("data", exist_ok=True)

OUTPUT_FILE = "data/ookla_johor.parquet"

JOHOR_BOUNDS = {
    "min_lat": 1.15,
    "max_lat": 2.70,
    "min_lon": 103.30,
    "max_lon": 104.30,
}

OOKLA_URL = "https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=fixed/year=2024/quarter=3/fixed_2024_q3_malaysia.parquet"


def tile_x_to_lon(x, z):
    return x / (2**z) * 360.0 - 180


def tile_y_to_lat(y, z):
    n = math.pi - (2.0 * math.pi * y) / (2**z)
    return 180.0 / math.pi * math.atan(math.sinh(n))


def download_ookla_parquet():
    local_file = "data/malaysia.parquet"

    if os.path.exists(local_file):
        return local_file

    print("Downloading Ookla Malaysia parquet...")
    r = requests.get(OOKLA_URL, stream=True)
    with open(local_file, "wb") as f:
        for chunk in r.iter_content(4096):
            f.write(chunk)

    print("Download completed.")
    return local_file


def process_johor(path):
    print("Processing Malaysia parquet...")
    df = pd.read_parquet(path)

    df["lon"] = df.apply(lambda r: tile_x_to_lon(r["tile_x"], r["tile_z"]), axis=1)
    df["lat"] = df.apply(lambda r: tile_y_to_lat(r["tile_y"], r["tile_z"]), axis=1)

    mask = (
        (df["lat"] >= JOHOR_BOUNDS["min_lat"]) &
        (df["lat"] <= JOHOR_BOUNDS["max_lat"]) &
        (df["lon"] >= JOHOR_BOUNDS["min_lon"]) &
        (df["lon"] <= JOHOR_BOUNDS["max_lon"])
    )

    out = df[mask].copy()
    out.rename(columns={
        "avg_d_kbps": "download",
        "avg_u_kbps": "upload",
        "avg_latency_ms": "latency",
        "provider_name": "provider"
    }, inplace=True)

    return out


if __name__ == "__main__":
    parquet = download_ookla_parquet()
    df = process_johor(parquet)
    df.to_parquet(OUTPUT_FILE, index=False)
    print("Saved:", OUTPUT_FILE)
