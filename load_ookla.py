import os
import zipfile
import pandas as pd
from shapely.geometry import shape, Polygon
from datetime import datetime

DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "ookla_johor.csv")

JOHOR_BOUNDS = Polygon([
    (103.0, 2.0),
    (104.5, 2.0),
    (104.5, 1.3),
    (103.0, 1.3)
])

def quarter_start(year: int, q: int):
    return datetime(year, (q - 1) * 3 + 1, 1)

def get_tile_url(service_type: str, year: int, q: int) -> str:
    dt = quarter_start(year, q)
    base_url = "https://ookla-open-data.s3.amazonaws.com/shapefiles/performance"
    return (
        f"{base_url}/type={service_type}/year={dt:%Y}/quarter={q}/"
        f"{dt:%Y-%m-%d}_performance_{service_type}_tiles.zip"
    )

def detect_latest_quarter():
    now = datetime.utcnow()
    year = now.year
    q = (now.month - 1) // 3 #+ 1
    return year, q

def download_file(url: str, out_path: str):
    import requests
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise RuntimeError(f"Download failed {r.status_code}: {url}")

    with open(out_path, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)

def extract_johor_tiles(zip_path: str):
    rows = []

    with zipfile.ZipFile(zip_path, "r") as z:
        # Find the .geojson tiles file
        geojson_name = None
        for name in z.namelist():
            if name.endswith(".geojson"):
                geojson_name = name
                break

        if not geojson_name:
            raise RuntimeError("GeoJSON tile file not found in ZIP.")

        # Load JSON manually
        import json
        with z.open(geojson_name) as f:
            data = json.load(f)

        for feature in data["features"]:
            geom = shape(feature["geometry"])
            if geom.intersects(JOHOR_BOUNDS):
                props = feature["properties"]
                rows.append(props)

    if not rows:
        raise RuntimeError("No Johor tiles found.")

    return pd.DataFrame(rows)

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("📡 Detecting latest quarter...")
    year, q = detect_latest_quarter()
    print(f"Using latest dataset: {year} Q{q}")

    url = get_tile_url("mobile", year, q)
    zip_path = os.path.join(DATA_DIR, "tiles.zip")

    print(f"⬇ Downloading mobile tiles:\n{url}")
    download_file(url, zip_path)
    print("✔ Download complete.")

    print("📦 Extracting Johor tiles...")
    df = extract_johor_tiles(zip_path)

    print(f"💾 Saving cleaned CSV → {OUTPUT_FILE}")
    df.to_csv(OUTPUT_FILE, index=False)

    print("🎉 Loader finished successfully!")

if __name__ == "__main__":
    main()
