# Ookla Johor Streamlit Dashboard

Interactive Streamlit app to load Ookla Open Data, focus on Johor (Malaysia), allow users to search a location or draw a polygon and compute 5km-radius averages (and polygon averages) per telco.

## Quickstart (local)
1. Create a virtualenv and activate it.
2. `pip install -r requirements.txt`
3. Run the data loader once (downloads latest quarter and writes `data/ookla_johor.geojson`):
   ```
   python load_ookla.py --output data/ookla_johor.gpkg
   ```
4. Run the Streamlit app:
   ```
   streamlit run app.py
   ```

## What it does
- Downloads latest Ookla mobile parquet files from the public AWS Open Data bucket (anonymous access).
- Filters points to Johor bounding box.
- Saves a GeoPackage and a GeoJSON used by the app.
- Streamlit app lets users search locations, click on map, draw polygons; computes per-operator averages within 5km radius or polygon.

## Notes
- Nominatim geocoding is used for search (rate limits). For production, consider caching or a commercial geocoder.
- For very large datasets, switch to PostGIS and pre-aggregations.
