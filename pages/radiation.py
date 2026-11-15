from datetime import datetime, timedelta
from io import StringIO

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ==========================================
# CONSTANTS
# ==========================================
DATA_MIN = datetime(2010, 1, 5, 9, 43)  # earliest reading in RadLab ISS data
DATA_MAX = datetime(2024, 11, 4, 13, 51)  # latest reading

# Typical absorbed dose inside the ISS Columbus module: 195-360 μGy/day
# (DOSIS / DOSIS 3D passive detectors, 2010-2012; Berger et al. 2016, J. Space Weather Space Clim.)
TYPICAL_ABS_DAILY = (0.195, 0.36)  # mGy/day
TYPICAL_ABS_BAND = tuple(v * 1000 / 24 for v in TYPICAL_ABS_DAILY)  # same range as μGy/h (~8.1-15)

# DEMO thresholds for the status banner (absorbed dose, mGy/day). NOT official NASA limits.
CAUTION_ABS_DAILY = 0.36  # top of the typical range
CRITICAL_ABS_DAILY = 0.72  # double the top of the typical range

# Most RadLab ISS instruments report absorbed dose only. Dose equivalent is estimated as
# absorbed dose x mean quality factor (Q). One DOSTEL measurement in 2016 reported 286 μGy/day
# absorbed and 647 μSv/day dose equivalent (Q ~ 2.3); the slider lets the user change Q.
DEFAULT_Q = 2.0

CAREER_LIMIT_MSV = 600  # NASA career effective-dose limit (NASA-STD-3001)
BACKGROUND_MSV_PER_DAY = 3 / 365  # ~3 mSv/year natural background on Earth
MISSION_DAYS = 182  # 6-month mission, used for the projection gauge


# ==========================================
# DATA
# ==========================================
@st.cache_data(show_spinner="Fetching from NASA RadLab...")
def get_iss_data(start: datetime, end: datetime) -> pd.DataFrame:
    fmt = lambda t: t.isoformat(timespec="minutes")
    fields = ["absorbed_dose_rate", "dose_equivalent_rate", "flux", "latitude", "longitude", "altitude", "B", "L"]
    url = "https://visualization.osdr.nasa.gov/radlab/api/?spacecraft=ISS&" + "&".join(fields) + f"&timestamp>={fmt(start)}&timestamp<={fmt(end)}&format=csv"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    if not r.text.strip():
        return pd.DataFrame()
    return pd.read_csv(StringIO(r.text), parse_dates=["timestamp"])


def add_cumulative(df, rate_col, out_col, min_gap_hours=1.0):
    """Cumulative dose per instrument (trapezoid rule). Output is /1000: μSv -> mSv or μGy -> mGy.
    A gap between readings is ignored if it is much longer than that instrument's usual spacing."""
    d = df.dropna(subset=[rate_col]).sort_values(["instrument_id", "timestamp"]).copy()
    g = d.groupby("instrument_id")
    hours = g["timestamp"].diff().dt.total_seconds().div(3600)
    usual = hours.groupby(d["instrument_id"]).transform("median")
    limit = (3 * usual).clip(lower=min_gap_hours)  # daily-average instruments get a longer limit
    avg_rate = (d[rate_col] + g[rate_col].shift()) / 2
    dose = (avg_rate * hours).where(hours <= limit, 0).fillna(0) / 1000
    d[out_col] = dose.groupby(d["instrument_id"]).cumsum()
    return d


def summarize(df, window_days):
    """Per-instrument summary. Expects absorbed_dose_rate (μGy/h) and de_rate (μSv/h)."""
    g = df.groupby("instrument_id")
    out = pd.DataFrame(
        {
            "readings": g.size(),
            "mean_abs": g["absorbed_dose_rate"].mean(),
            "peak_abs": g["absorbed_dose_rate"].max(),
            "mean_de": g["de_rate"].mean(),
            "first": g["timestamp"].min(),
            "last": g["timestamp"].max(),
        }
    )
    out["mgy_per_day"] = out["mean_abs"] * 24 / 1000
    out["msv_per_day"] = out["mean_de"] * 24 / 1000
    span_seconds = (out["last"] - out["first"]).dt.total_seconds()
    out["coverage_pct"] = (span_seconds / (window_days * 86400)).clip(upper=1) * 100
    return out


def classify(mgy_per_day):
    if mgy_per_day > CRITICAL_ABS_DAILY:
        return (
            "CRITICAL ALERT",
            "Dose rate is far above the typical range inside the ISS. Notify the Flight Surgeon and mission "
            "control, check space-weather alerts, and follow solar-particle-event procedures.",
        )
    if mgy_per_day > CAUTION_ABS_DAILY:
        return (
            "CAUTION",
            "Dose rate is above the typical range inside the ISS. Check space-weather alerts (NOAA SWPC) and inform the radiation officer.",
        )
    return "NOMINAL", "Radiation levels are within the typical range inside the ISS. No action needed."


# ==========================================
# CHARTS
# ==========================================
def line(data, y, title, band=None, y_max=None):
    zoom = alt.selection_interval(bind="scales", encodings=["x"])
    y_scale = alt.Scale(domain=[0, y_max]) if y_max else alt.Scale(domainMin=0)
    lines = (
        alt.Chart(data)
        .mark_line(point=False, clip=True)
        .encode(
            x=alt.X("timestamp:T", title="Time (UTC)"),
            y=alt.Y(f"{y}:Q", title=title, scale=y_scale),
            color=alt.Color("instrument_id:N", title="Instrument"),
            tooltip=["timestamp:T", "instrument_id:N", f"{y}:Q"],
        )
        .add_params(zoom)
    )
    if not band:
        return lines
    box = pd.DataFrame({"x0": [data["timestamp"].min()], "x1": [data["timestamp"].max()], "lo": [band[0]], "hi": [band[1]]})
    shade = alt.Chart(box).mark_rect(opacity=0.2, color="green", clip=True).encode(x=alt.X("x0:T", title="Time (UTC)"), x2="x1:T", y=alt.Y("lo:Q", title=title), y2="hi:Q")
    edges = alt.Chart(pd.DataFrame({"v": list(band)})).mark_rule(color="green", strokeDash=[4, 4], opacity=0.7, clip=True).encode(y=alt.Y("v:Q", title=title))
    return alt.layer(shade, edges, lines)


def gauge(value, title, max_value, steps):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title, "font": {"size": 18}},
            gauge={"axis": {"range": [0, max_value]}, "bar": {"color": "#2196F3"}, "steps": steps},
        )
    )
    fig.update_layout(height=290, margin=dict(l=30, r=30, t=90, b=20))
    return fig


# ==========================================
# HEADER
# ==========================================
st.title("☢️ Space Radiation Monitor")
st.markdown(
    """
**Mission Goal:** Astronauts on the ISS are exposed to more radiation than people on Earth, and the amount changes
with the orbit and with solar activity. Pick a start date and a duration, and this tool shows how much radiation the
station's detectors recorded, and whether it is within the normal range.
"""
)

# --- SIDEBAR ATTRIBUTION ---
st.sidebar.header("📁 Data Source")
st.sidebar.markdown(
    """
Radiation data comes from the **NASA Open Science Data Repository (OSDR) RadLab** database.
* **Measurements:** ISS radiation detectors (e.g. DosTel, Lidal, REM, TEPC)
* **Coverage:** 2010-01-05 to 2024-11-04
* **Note:** most ISS detectors in RadLab report *absorbed dose*. Dose equivalent is estimated from it.
"""
)
st.sidebar.markdown("[🔗 View RadLab Data Portal](https://visualization.osdr.nasa.gov/radlab/gui/data-overview/)")

# ==========================================
# INPUTS
# ==========================================
with st.expander("❓ What do these numbers mean? (Click to expand)", expanded=True):
    st.markdown(
        f"""
* **Absorbed dose (mGy):** Think of this as **energy soaked up**. It is the raw physical amount of radiation energy
  absorbed. This is what most ISS detectors measure, so the status below is based on it.
    * Typical inside the ISS: about **{TYPICAL_ABS_DAILY[0]}–{TYPICAL_ABS_DAILY[1]} mGy per day**
* **Dose equivalent (mSv):** Think of this as **damage done to the body**. Different kinds of radiation harm tissue by
  different amounts. It is the absorbed dose multiplied by a **quality factor (Q)**, and it is the number health limits
  are written in. If a detector doesn't report it, this tool **estimates** it using the Q you choose.
* **For comparison:** natural background radiation on Earth is about 3 mSv per *year*, and NASA's career limit is
  **{CAREER_LIMIT_MSV} mSv** of total effective dose.
"""
    )

st.markdown("Choose when to start and how long to look at.")

c1, c2, c3 = st.columns([2, 1, 1])
start = c1.datetime_input(
    "Start (UTC)",
    min_value=DATA_MIN,
    max_value=DATA_MAX,
    value=datetime(2022, 1, 1),
    help="Data exists between 2010-01-05 and 2024-11-04.",
)
duration = c2.number_input("Duration", min_value=0.0, value=1.0, step=1.0, format="%g")
unit = c3.selectbox("Unit", ["days", "hours"])
end = start + (timedelta(days=duration) if unit == "days" else timedelta(hours=duration))

if duration <= 0:
    st.error("Duration must be greater than zero.")
    st.stop()

st.caption(f"Window: {start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M} UTC")

st.write("")
run_btn = st.button("▶ RUN RADIATION CHECK", type="primary", width="stretch")

if run_btn:
    try:
        st.session_state["rad_df"] = get_iss_data(start, end)
        st.session_state["rad_range"] = (start, end)
    except requests.RequestException as e:
        st.error(f"Request failed: {e}")

# ==========================================
# RESULTS
# ==========================================
df = st.session_state.get("rad_df")

if df is None:
    st.info("Pick a start date and duration, then press **RUN RADIATION CHECK**.")
    st.stop()
if df.empty:
    st.warning("No data available for that window. Try another date between 2010 and 2024.")
    st.stop()

r_start, r_end = st.session_state["rad_range"]
window_days = (r_end - r_start) / timedelta(days=1)

st.divider()

f1, f2 = st.columns([3, 1])
instruments = sorted(df["instrument_id"].dropna().unique())
chosen = f1.multiselect("Instruments to include", instruments, default=instruments)
q = f2.slider(
    "Quality factor (Q)",
    min_value=1.0,
    max_value=4.0,
    value=DEFAULT_Q,
    step=0.1,
    help="Used only to estimate dose equivalent from absorbed dose when a detector doesn't report it.",
)
if not chosen:
    st.warning("Select at least one instrument.")
    st.stop()
df = df[df["instrument_id"].isin(chosen)].copy()

# Dose equivalent: use the measured value when present, otherwise estimate it from absorbed dose.
df["de_rate"] = df["dose_equivalent_rate"].fillna(df["absorbed_dose_rate"] * q)
share_estimated = (df["dose_equivalent_rate"].isna() & df["absorbed_dose_rate"].notna()).sum() / max(df["de_rate"].notna().sum(), 1)

abs_rows = df.dropna(subset=["absorbed_dose_rate"])

if abs_rows.empty:
    st.info("These instruments did not report **absorbed dose** in this window, so a health status can't be calculated. Try a different date or other instruments.")
else:
    summary = summarize(abs_rows, window_days)
    station_mgy_day = summary["mgy_per_day"].median()  # median across instruments
    station_msv_day = summary["msv_per_day"].median()
    station_dose_msv = station_msv_day * window_days
    peak_abs = summary["peak_abs"].max()
    coverage = summary["coverage_pct"].median()

    risk_level, action_text = classify(station_mgy_day)

    # 1. BIG STATUS BANNER
    if risk_level == "CRITICAL ALERT":
        st.error(f"### 🚨 RADIATION STATUS: {risk_level}")
        st.error(f"**What to do next:** {action_text}")
    elif risk_level == "CAUTION":
        st.warning(f"### ⚠️ RADIATION STATUS: {risk_level}")
        st.warning(f"**What to do next:** {action_text}")
    else:
        st.success(f"### ✅ RADIATION STATUS: {risk_level}")
        st.success(f"**What to do next:** {action_text}")
    st.caption(
        f"Status is based on the average absorbed dose per day. Caution above {CAUTION_ABS_DAILY} mGy/day (top of "
        f"the typical range) and critical above {CRITICAL_ABS_DAILY} mGy/day are this app's demo thresholds, "
        "not official NASA limits."
    )

    st.write("")

    # 2. READOUTS
    st.markdown("#### 📡 Radiation Overview")
    est_tag = " (estimated)" if share_estimated > 0.5 else ""
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Dose equivalent in window{est_tag}", f"{station_dose_msv:.3f} mSv")
    m2.metric("Average absorbed dose", f"{station_mgy_day:.3f} mGy/day")
    m3.metric("Peak absorbed rate", f"{peak_abs:.1f} μGy/h")
    m4.metric("Data coverage", f"{coverage:.0f}%")

    background_days = station_dose_msv / BACKGROUND_MSV_PER_DAY
    pct_limit = station_dose_msv / CAREER_LIMIT_MSV * 100
    st.caption(
        f"That is about **{background_days:.1f} days** of natural background radiation on Earth, and "
        f"**{pct_limit:.2f}%** of NASA's {CAREER_LIMIT_MSV} mSv career limit. "
        "These are station detector readings, not any individual astronaut's dose."
    )
    if share_estimated > 0:
        st.info(
            f"**{share_estimated:.0%}** of the dose-equivalent values are **estimated** as absorbed dose × Q (Q = {q:.1f}). Move the Q slider to see how the estimate changes."
        )

    # 3. GAUGES
    st.markdown("#### 📊 Health Thresholds (Green is Normal, Red is High)")
    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(
            gauge(
                station_mgy_day,
                "Average Absorbed Dose (mGy/day)",
                1.0,
                [
                    {"range": [0, CAUTION_ABS_DAILY], "color": "#21c354"},
                    {"range": [CAUTION_ABS_DAILY, CRITICAL_ABS_DAILY], "color": "#ffa421"},
                    {"range": [CRITICAL_ABS_DAILY, 1.0], "color": "#ff4b4b"},
                ],
            ),
            width="stretch",
        )
    with g2:
        projected = station_msv_day * MISSION_DAYS
        green_top = CAUTION_ABS_DAILY * q * MISSION_DAYS
        orange_top = CRITICAL_ABS_DAILY * q * MISSION_DAYS
        gauge_max = orange_top * 1.4
        st.plotly_chart(
            gauge(
                projected,
                f"Projected {MISSION_DAYS}-Day Dose (mSv)",
                gauge_max,
                [
                    {"range": [0, green_top], "color": "#21c354"},
                    {"range": [green_top, orange_top], "color": "#ffa421"},
                    {"range": [orange_top, gauge_max], "color": "#ff4b4b"},
                ],
            ),
            width="stretch",
        )
    st.caption(
        "The projection assumes the same daily dose continues for the whole mission. "
        "For reference, one NASA paper gives about 40–90 mSv of effective dose over a typical six-month ISS mission; "
        "effective dose is lower than the detector-based dose equivalent shown here."
    )

    with st.expander("Per-instrument breakdown"):
        table = summary.rename(
            columns={
                "readings": "Readings",
                "mean_abs": "Mean absorbed (μGy/h)",
                "peak_abs": "Peak absorbed (μGy/h)",
                "mean_de": "Mean dose equiv. (μSv/h)",
                "mgy_per_day": "mGy/day",
                "msv_per_day": "mSv/day",
                "coverage_pct": "Coverage (%)",
            }
        ).drop(columns=["first", "last"])
        st.dataframe(table.round(3), width="stretch")

# ==========================================
# TIME SERIES
# ==========================================
st.markdown("#### 📈 Radiation Over Time")

eq = add_cumulative(df, "de_rate", "cum_msv")
ab = add_cumulative(df, "absorbed_dose_rate", "cum_mgy")

panels = []
if df["absorbed_dose_rate"].notna().any():
    panels.append(("Absorbed dose", "absorbed_dose_rate", "Rate (μGy/h)", ab, "cum_mgy", "Cumulative (mGy)", TYPICAL_ABS_BAND))
if df["de_rate"].notna().any():
    label = "Dose equivalent (estimated)" if share_estimated > 0 else "Dose equivalent"
    panels.append((label, "de_rate", "Rate (μSv/h)", eq, "cum_msv", "Cumulative (mSv)", None))

if not panels:
    st.warning("No dose readings in this window.")
else:
    y_max = st.number_input("Rate chart Y-axis max (0 = auto)", min_value=0.0, value=0.0, step=5.0, format="%g") or None
    tabs = st.tabs([p[0] for p in panels])
    for tab, (label, rate_col, rate_title, cum_df, cum_col, cum_title, band) in zip(tabs, panels):
        with tab:
            st.altair_chart(
                line(df.dropna(subset=[rate_col]), rate_col, rate_title, band=band, y_max=y_max),
                width="stretch",
            )
            if band:
                st.caption("Green band = typical absorbed dose inside the ISS Columbus module (195–360 μGy/day, DOSIS measurements 2010–2012).")
            if not cum_df.empty:
                st.altair_chart(line(cum_df, cum_col, cum_title), width="stretch")

with st.expander("Raw data"):
    st.dataframe(df, width="stretch")
