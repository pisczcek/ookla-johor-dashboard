import os
import pandas as pd
import requests
import math

os.makedirs("data", exist_ok=True)
OUTPUT_FILE = "data/ookla_johor.parquet"

# Use a Malaysia parquet file - adjust quarter/year as needed
OOKLA_URL = "https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=fixed/year=2024/quarter=3/fixed_2024_q3_malaysia.parquet"

JOHOR_BOUNDS = {
    "min_lon": 103.3,
    "max_lon": 104.3,
    "min_lat": 1.15,
    "max_lat": 2.7,
}

def tile_x_to_lon(x, z):
    return x / (2**z) * 360.0 - 180

def tile_y_to_lat(y, z):
    n = math.pi - (2.0 * math.pi * y) / (2**z)
    return 180.0 / math.pi * math.atan(math.sinh(n))

def download():
    local = "data/malaysia.parquet"
    if os.path.exists(local):
        print("Malaysia parquet already exists")
        return local
    print("Downloading Malaysia parquet...")
    r = requests.get(OOKLA_URL, stream=True)
    r.raise_for_status()
    with open(local, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return local

def process(path):
    print("Loading parquet...")
    df = pd.read_parquet(path)
    # convert tile x/y/z to lon/lat if available, else use existing lat/lon columns
    if 'tile_x' in df.columns and 'tile_y' in df.columns and 'tile_z' in df.columns:
        df['tile_lon'] = df.apply(lambda r: tile_x_to_lon(r['tile_x'], r['tile_z']), axis=1)
        df['tile_lat'] = df.apply(lambda r: tile_y_to_lat(r['tile_y'], r['tile_z']), axis=1)
    elif 'tile_lon' in df.columns and 'tile_lat' in df.columns:
        df['tile_lon'] = df['tile_lon']
        df['tile_lat'] = df['tile_lat']
    else:
        raise RuntimeError("No coordinate columns found in parquet")

    # filter Johor bounding box
    df = df[
        (df['tile_lon'] >= JOHOR_BOUNDS['min_lon']) &
        (df['tile_lon'] <= JOHOR_BOUNDS['max_lon']) &
        (df['tile_lat'] >= JOHOR_BOUNDS['min_lat']) &
        (df['tile_lat'] <= JOHOR_BOUNDS['max_lat'])
    ].copy()

    # rename common columns for app convenience (fall back to existing names)
    df.rename(columns={
        'avg_d_kbps': 'avg_d_kbps',
        'avg_u_kbps': 'avg_u_kbps',
        'avg_latency_ms': 'avg_latency_ms',
        'provider_name': 'provider_name'
    }, inplace=True)

    df.to_parquet(OUTPUT_FILE, index=False)
    print("Saved", OUTPUT_FILE)

if __name__ == '__main__':
    p = download()
    process(p)
