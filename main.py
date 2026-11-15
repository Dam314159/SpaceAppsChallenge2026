import streamlit as st

st.set_page_config(page_title="Nasa Space Apps 2026 Health Montioring by Group 17", page_icon="🏥", layout="wide")

# Change this if you want to add or change the pages
home = st.Page("pages/home.py", title="Home page", default=True)
radiation = st.Page("pages/radiation.py", title="Radiation")
third_page = st.Page("pages/third_page.py", title="Third Page", icon=":material/home:")

# Change this if you want to add or change the pages
pg = st.navigation(
    [
        "pages/home.py",
        "pages/radiation.py",
        "pages/sleep.py"
    ]
)

pg.run()
