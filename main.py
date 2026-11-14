import streamlit as st

st.set_page_config(page_title="Nasa Space Apps 2026 Health Montioring by Group 17", page_icon="🏥", layout="wide")

# Change this if you want to add or change the pages
first_page = st.Page("pages/first_page.py", title="First Page", icon=":material/home:", default=True)
second_page = st.Page("pages/second_page.py", title="Second Page", icon=":material/home:")
third_page = st.Page("pages/third_page.py", title="Third Page", icon=":material/home:")

# Change this if you want to add or change the pages
pg = st.navigation(
    {
        "One": [first_page],
        "Too": [second_page, third_page],
    }
)

pg.run()