import os
import pandas as pd
import requests

os.makedirs("data", exist_ok=True)
OUTPUT_FILE = "data/ookla_johor.parquet"

OOKLA_URL = "https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=fixed/year=2024/quarter=3/fixed_2024_q3_malaysia.parquet"

# Johor bounding box
JOHOR_BOUNDS = {
    "min_lon": 103.3,
    "max_lon": 104.3,
    "min_lat": 1.15,
    "max_lat": 2.7,
}

def download():
    print("Downloading Ookla Malaysia parquet…")
    r = requests.get(OOKLA_URL, stream=True)
    r.raise_for_status()
    local_file = "data/malaysia.parquet"
    with open(local_file, "wb") as f:
        for chunk in r.iter_content(4096):
            f.write(chunk)
    return local_file

def process(path):
    print("Filtering Johor…")
    df = pd.read_parquet(path)
    df = df[
        (df['tile_lat'] >= JOHOR_BOUNDS['min_lat']) &
        (df['tile_lat'] <= JOHOR_BOUNDS['max_lat']) &
        (df['tile_lon'] >= JOHOR_BOUNDS['min_lon']) &
        (df['tile_lon'] <= JOHOR_BOUNDS['max_lon'])
    ]
    df.to_parquet(OUTPUT_FILE, index=False)
    print("Saved:", OUTPUT_FILE)

if __name__ == "__main__":
    p = download()
    process(p)
