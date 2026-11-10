# ⛽ Pakistan Live Petrol & Diesel Prices (Streamlit)

Live OGRA petrol and diesel prices from the free AutoOnes API (no key needed).

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Features
- Live current petrol & diesel price cards with the latest change (red = increase, green = cut)
- Price history charts in daily, monthly (with min–max band) or yearly view, 1–400 records
- Low, high and net change stats for the selected period
- Table of recent price revisions
- Fuel cost calculator (by litres or by distance and mileage)
- CSV download of the history
- Caching matches the API (5 min current, 10 min history), plus a manual Refresh button

## Deploy free
Push `app.py` + `requirements.txt` to GitHub → share.streamlit.io → New app → select `app.py`.

## API
- `GET https://api2.autoones.com/api/fuel-prices`
- `GET https://api2.autoones.com/api/fuel-prices/history?fuel=petrol|diesel&view=daily|monthly|yearly&limit=1..400`
"# petrolprice" 
