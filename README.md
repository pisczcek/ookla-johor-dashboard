# Ookla Johor Explorer (Upgraded)

This repository contains a Streamlit app that downloads Ookla Open Data and provides:
- 5km radius averages per operator
- Polygon draw aggregation (folium draw)
- Operator logos/colors + charts
- Streamlit Cloud compatible (minimal heavy native libs)

## Files
- `app.py` — main Streamlit app
- `load_ookla.py` — downloads Ookla Malaysia parquet, filters Johor, saves parquet
- `requirements.txt` — Python dependencies
- `.streamlit/config.toml` — UI config
- `assets/operators.json` — operator metadata (logos/colors)

## Run locally
```bash
pip install -r requirements.txt
python load_ookla.py
streamlit run app.py
```

## License & Attribution
Data: Ookla Open Data — https://github.com/teamookla/ookla-open-data  
Licensed under CC BY-NC-SA 4.0 — attribution required.
