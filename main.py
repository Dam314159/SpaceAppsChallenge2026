import streamlit as st

st.set_page_config(page_title="Nasa Space Apps 2026 Health Montioring by Group 17", page_icon="🏥", layout="wide")

# Change this if you want to add or change the pages
home = st.Page("pages/home.py", title="Home", default=True)
radiation = st.Page("pages/radiation.py", title="Radiation")
sleep = st.Page("pages/sleep.py", title="Sleep")

# Change this if you want to add or change the pages
pg = st.navigation(
    [
        home,
        radiation,
        sleep,
    ]
)

pg.run()
