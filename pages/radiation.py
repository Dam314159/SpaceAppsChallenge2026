from datetime import datetime, timedelta

# import pandas as pd
import requests
import streamlit as st


def get_iss_data(start: datetime, end: datetime | None = None):
    end = end or start + timedelta(hours=1)
    fmt = lambda t: t.isoformat(timespec="minutes")

    fields = ["absorbed_dose_rate", "dose_equivalent_rate", "flux", "latitude", "longitude", "altitude", "B", "L"]
    url = "https://visualization.osdr.nasa.gov/radlab/api/?spacecraft=ISS&" + "&".join(fields) + f"&timestamp>={fmt(start)}&timestamp<{fmt(end)}&format=csv"

    r = requests.get(url, timeout=120)
    r.raise_for_status()
    with open("data/iss_rad.csv", "wb") as f:
        f.write(r.content)


get_iss_data(datetime(2021, 4, 1, 23, 0))

st.write("This is streamlit text")
