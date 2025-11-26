import os
import requests
import zipfile
import pandas as pd
import math

OUTPUT_DIR = "data"
OUTPUT_FILE = f"{OUTPUT_DIR}/ookla_johor.parquet"

# Malaysia bounding box
JOHOR_BOUNDS = {
    "min_lat": 1.15,
    "max_lat": 2.70,
    "min_lon": 103.30,
    "max_lon": 104.30,
}

# Ookla latest dataset (2024Q3 now, change when needed)
OOKLA_URL = "https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=fixed/year=2024/quarter=3/fixed_2024_q3_malaysia.parquet"


# -------------------------------------------------------------------
# Convert tile xyz → latitude / longitude
# -------------------------------------------------------------------

def tile_x_to_lon(x, z):
    return x / (2**z) * 360.0 - 180


def tile_y_to_lat(y, z):
    n = math.pi - (2.0 * math.pi * y) / (2**z)
    return 180.0 / math.pi * math.atan(math.sinh(n))


# -------------------------------------------------------------------
# Load Ookla Malaysia parquet
# -------------------------------------------------------------------

def download_ookla_parquet():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    local_file = f"{OUTPUT_DIR}/malaysia.parquet"

    if os.path.exists(local_file):
        print("✔ Malaysia parquet already downloaded.")
        return local_file

    print("⬇ Downloading Malaysia Ookla data...")
    
    response = requests.get(OOKLA_URL, stream=True)
    if response.status_code != 200:
        raise Exception(f"Failed to download: HTTP {response.status_code}")

    with open(local_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=4096):
            f.write(chunk)

    print("✔ Download complete.")
    return local_file


# -------------------------------------------------------------------
# Filter only Johor
# -------------------------------------------------------------------

def process_johor(input_parquet):
    print("📦 Loading Malaysia parquet...")
    df = pd.read_parquet(input_parquet)

    print("📍 Converting tiles to lat/lon...")

    df["lon"] = df.apply(lambda r: tile_x_to_lon(r["tile_x"], r["tile_z"]), axis=1)
    df["lat"] = df.apply(lambda r: tile_y_to_lat(r["tile_y"], r["tile_z"]), axis=1)

    print("🔍 Filtering Johor...")

    mask = (
        (df["lat"] >= JOHOR_BOUNDS["min_lat"]) &
        (df["lat"] <= JOHOR_BOUNDS["max_lat"]) &
        (df["lon"] >= JOHOR_BOUNDS["min_lon"]) &
        (df["lon"] <= JOHOR_BOUNDS["max_lon"])
    )

    df_johor = df[mask].copy()

    print(f"✔ Johor tiles extracted: {len(df_johor)} rows")

    return df_johor


# -------------------------------------------------------------------
# Save to final parquet
# -------------------------------------------------------------------

def save_output(df):
    df.to_parquet(OUTPUT_FILE, index=False)
    print(f"✔ Saved: {OUTPUT_FILE}")


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Ookla Loader Started ===")

    parquet_file = download_ookla_parquet()
    df = process_johor(parquet_file)
    save_output(df)

    print("=== DONE ===")
