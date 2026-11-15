import streamlit as st

st.set_page_config(page_title="Nasa Space Apps 2026 Health Monitoring by Group 17", page_icon="🏥", layout="wide")

# Change this if you want to add or change the pages
home = st.Page("pages/home.py", title="Home page", default=True)
radiation = st.Page("pages/radiation.py", title="Radiation")
reflex = st.Page("pages/reflex_monitoring.py", title="Reflex Monitoring", icon="🦵")
sleep = st.Page("pages/sleep.py", title="Sleep")

# Change this if you want to add or change the pages
pg = st.navigation(
    [
        "pages/home.py",
        "pages/radiation.py",
        "pages/sleep.py",
        "pages/reflex_monitoring.py"
    ]
)

pg.run()