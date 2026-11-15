from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Sleep & Actigraphy Monitor", page_icon="🌙", layout="wide")

DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "BRSMACT_Campagin_1_Actigraphy.csv"
)
MIN_REFERENCE_ROWS = 10
PHASE_ORDER = ["PRE_TEST", "IN_TEST", "POST_TEST"]


# --- HEADER ---
st.title("🌙 Sleep & Actigraphy Monitor")
st.markdown("""
**Mission Goal:** Sleep can be disrupted during long-duration missions.
Review sleep records, track new readings, and compare them with the observed
range for a study phase.
""")

# --- SIDEBAR ATTRIBUTION ---
st.sidebar.header("📁 Data Source")
st.sidebar.markdown("""
The reference dataset is sourced from the **NASA Life Sciences Data Archive**.
* **Experiment:** Bed Rest Standard Measures: Actilight (BRSMACT)
* **Investigator:** Lakshmi Putcha (NASA)
""")
st.sidebar.markdown(
    "[🔗 View Official NASA Data Portal]"
    "(https://nlsp.nasa.gov/search/data/details/"
    "cd8a4a16-fcfd-5c32-a61f-22c590a10b35?dataType=EXPERIMENTS)"
)


# --- DATA LOADING ---
@st.cache_data
def load_actigraphy() -> pd.DataFrame:
    data = pd.read_csv(DATA_PATH, na_values=["NA", "N/A", ""])
    required_columns = {
        "Subject",
        "Test_Phase",
        "BR_Day",
        "Date",
        "Sleep Duration (hours)",
        "Sleep Efficiency (%)",
    }
    missing_columns = required_columns.difference(data.columns)
    if missing_columns:
        raise ValueError(
            f"Actigraphy data is missing columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    duration_values = data["Sleep Duration (hours)"]
    numeric_hours = pd.to_numeric(duration_values, errors="coerce")
    parsed_hours = (
        pd.to_timedelta(duration_values, errors="coerce").dt.total_seconds() / 3600
    )
    data["sleep_hours"] = numeric_hours.where(
        numeric_hours.notna(), parsed_hours
    )
    data["Sleep Efficiency (%)"] = pd.to_numeric(
        data["Sleep Efficiency (%)"], errors="coerce"
    )
    return data


def normalize_imported_records(upload: pd.DataFrame) -> pd.DataFrame:
    """Accept common date, sleep-duration, and efficiency column names."""
    column_lookup = {
        str(column).strip().lower().replace("_", " "): column
        for column in upload.columns
    }

    date_column = next(
        (
            column_lookup[name]
            for name in ("date", "sleep date", "datetime")
            if name in column_lookup
        ),
        None,
    )
    duration_column = next(
        (
            column_lookup[name]
            for name in (
                "sleep duration (hours)",
                "sleep duration",
                "sleep hours",
                "duration hours",
                "hours slept",
            )
            if name in column_lookup
        ),
        None,
    )
    efficiency_column = next(
        (
            column_lookup[name]
            for name in ("sleep efficiency (%)", "sleep efficiency", "efficiency")
            if name in column_lookup
        ),
        None,
    )

    if date_column is None or duration_column is None:
        raise ValueError(
            "CSV needs a date column and a sleep-duration column. "
            "Accepted duration headers include 'Sleep Duration (hours)' "
            "and 'sleep_hours'."
        )

    records = pd.DataFrame()
    records["Date"] = pd.to_datetime(upload[date_column], errors="coerce")

    duration_values = upload[duration_column]
    numeric_hours = pd.to_numeric(duration_values, errors="coerce")
    parsed_hours = (
        pd.to_timedelta(duration_values, errors="coerce").dt.total_seconds() / 3600
    )
    records["sleep_hours"] = numeric_hours.where(
        numeric_hours.notna(), parsed_hours
    )

    if efficiency_column is not None:
        records["Sleep Efficiency (%)"] = pd.to_numeric(
            upload[efficiency_column], errors="coerce"
        )
    else:
        records["Sleep Efficiency (%)"] = float("nan")

    records = records.dropna(subset=["Date", "sleep_hours"])
    if records.empty:
        raise ValueError("The CSV contains no valid dated sleep-duration records.")
    return records.sort_values("Date")

def get_sleep_status(
    records: pd.DataFrame,
    selected_index: int,
    lower_bound: float,
    upper_bound: float,
) -> tuple[bool, int]:
    """Return whether the selected night is outside range and its streak."""
    selected_date = pd.Timestamp(records.loc[selected_index, "Date"]).normalize()

    daily_records = (
        records.assign(_day=pd.to_datetime(records["Date"]).dt.normalize())
        .groupby("_day")["sleep_hours"]
        .mean()
        .sort_index()
    )

    streak = 0
    previous_day = None
    selected_is_outside = False
    selected_streak = 0

    for day, hours in daily_records.items():
        outside = hours < lower_bound or hours > upper_bound

        if outside:
            streak = (
                streak + 1
                if previous_day is not None and (day - previous_day).days == 1
                else 1
            )
        else:
            streak = 0

        if day == selected_date:
            selected_is_outside = outside
            selected_streak = streak

        previous_day = day

    return selected_is_outside, selected_streak





# --- TABS ---
tab_check, tab_history = st.tabs(
    ["🩺 Sleep Check", "📊 Historical Trends"]
)

try:
    actigraphy = load_actigraphy()
except (OSError, ValueError) as error:
    st.error(f"Could not load the actigraphy dataset: {error}")
    st.stop()

valid_data = actigraphy.dropna(
    subset=["Date", "sleep_hours", "Subject", "Test_Phase"]
)
if valid_data.empty:
    st.warning("No complete sleep records were found in the actigraphy dataset.")
    st.stop()


# ==========================================
# TAB 1: SLEEP CHECK
# ==========================================
with tab_check:
    st.subheader("Review and Record Sleep")
    st.info(
        "Study comparisons are descriptive, not clinical thresholds or diagnoses. "
        "Follow mission medical protocols for health concerns."
    )

    phase = "IN_TEST"
    phase_data = valid_data[valid_data["Test_Phase"] == phase]
    if phase_data.empty:
        st.warning("No complete crew records are available for the IN_TEST phase.")
        st.stop()

    reference_values = phase_data["sleep_hours"].dropna()
    has_reference = len(reference_values) >= MIN_REFERENCE_ROWS

    if has_reference:
        reference_low = reference_values.quantile(0.10)
        reference_high = reference_values.quantile(0.90)

    st.markdown("#### Import or manually enter sleep data")
    entry_method = st.radio(
        "Choose an entry method",
        ["Manual entry", "Import sleep data"],
        horizontal=True,
        key="sleep_entry_method",
    )

    new_records = pd.DataFrame()

    if entry_method == "Import sleep data":
        uploaded_file = st.file_uploader(
            "Import sleep data (.csv)",
            type="csv",
            help=(
                "Include a date and sleep duration column. Sleep efficiency "
                "is optional."
            ),
            key="sleep_data_upload",
        )
        if uploaded_file is not None:
            try:
                new_records = normalize_imported_records(
                    pd.read_csv(uploaded_file)
                )
                st.success(f"Imported {len(new_records)} sleep record(s).")
                st.dataframe(new_records, use_container_width=True)
            except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as error:
                st.error(f"Could not import sleep data: {error}")

    else:
        with st.form("manual_sleep_entry"):
            entry_date = st.date_input("Sleep date")
            entry_hours = st.number_input(
                "Sleep duration (hours)",
                min_value=0.0,
                max_value=24.0,
                value=8.0,
                step=0.25,
            )
            entry_efficiency = st.number_input(
                "Sleep efficiency (%)",
                min_value=0.0,
                max_value=100.0,
                value=85.0,
                step=1.0,
            )
            save_entry = st.form_submit_button(
                "Save sleep entry",
                type="primary",
                use_container_width=True,
            )

        if save_entry:
            if "manual_sleep_entries" not in st.session_state:
                st.session_state.manual_sleep_entries = []

            st.session_state.manual_sleep_entries.append(
                {
                    "Date": pd.Timestamp(entry_date),
                    "sleep_hours": float(entry_hours),
                    "Sleep Efficiency (%)": float(entry_efficiency),
                }
            )
            st.success("Sleep entry saved.")

        if st.session_state.get("manual_sleep_entries"):
            new_records = pd.DataFrame(st.session_state.manual_sleep_entries)
            st.markdown("**Manually entered records**")
            st.dataframe(
                new_records.sort_values("Date", ascending=False),
                use_container_width=True,
            )

    if not new_records.empty:
        latest_record = new_records.sort_values("Date").iloc[-1]
        st.markdown("#### Latest entered reading")
        metric_columns = st.columns(2)
        with metric_columns[0]:
            st.metric("Sleep duration", f"{latest_record['sleep_hours']:.1f} h")
        with metric_columns[1]:
            efficiency = latest_record["Sleep Efficiency (%)"]
            st.metric(
                "Sleep efficiency",
                f"{efficiency:.1f}%" if pd.notna(efficiency) else "Not recorded",
            )

        if has_reference:
            st.caption(
                f"Observed {phase} range: {reference_low:.1f}–"
                f"{reference_high:.1f} hours (10th–90th percentiles)."
            )
            if (
                latest_record["sleep_hours"] < reference_low
                or latest_record["sleep_hours"] > reference_high
            ):
                st.warning(
                    "This reading is outside the observed study range. "
                    "Verify the measurement and follow mission medical "
                    "protocols if changes persist or symptoms occur."
                )
            else:
                st.success("This reading is within the observed study range.")
        else:
            st.warning(
                f"Fewer than {MIN_REFERENCE_ROWS} complete records are available "
                f"for {phase}; a study-range comparison is not shown."
            )

    st.divider()
    st.subheader("Historical Study Record")

    subject_options = sorted(phase_data["Subject"].dropna().unique())
    if not subject_options:
        st.warning("No subjects with complete records are available for this phase.")
    else:
        default_subject = subject_options[0]
        if phase == "IN_TEST":
            lowest_record = phase_data.loc[phase_data["sleep_hours"].idxmin()]
            default_subject = lowest_record["Subject"]

        subject = st.selectbox(
            "Crew Member",
            subject_options,
            index=subject_options.index(default_subject),
            key="sleep_check_subject",
        )

        subject_records = (
            phase_data[phase_data["Subject"] == subject].sort_values("Date")
        )
        record_indexes = subject_records.index.tolist()
        default_record_index = subject_records["sleep_hours"].idxmin()

        selected_index = st.selectbox(
            "Historical night",
            record_indexes,
            index=record_indexes.index(default_record_index),
            format_func=lambda index: (
                f"{subject_records.loc[index, 'Date']:%b %d, %Y} "
                f"(BR day {subject_records.loc[index, 'BR_Day']})"
            ),
        )
        selected_record = subject_records.loc[selected_index]

        metric_columns = st.columns(2)
        with metric_columns[0]:
            st.metric(
                "Sleep duration",
                f"{selected_record['sleep_hours']:.1f} h",
            )
        with metric_columns[1]:
            efficiency = selected_record["Sleep Efficiency (%)"]
            st.metric(
                "Sleep efficiency",
                f"{efficiency:.1f}%" if pd.notna(efficiency) else "Not recorded",
            )

        if has_reference:
            outside, streak = get_sleep_status(
                subject_records,
                selected_index,
                reference_low,
                reference_high,
            )

            if not outside:
                st.success(
                    "✅ STATUS: NOMINAL — Sleep is within the observed range."
                )
            elif streak > 3:
                st.error(
                    f"🚨 STATUS: ALERT — Sleep has been outside the "
                    f"observed range for {streak} consecutive days. "
                    "Follow mission medical protocols."
                )
            else:
                st.warning(
                    f"⚠️ STATUS: CAUTION — Sleep has been outside the "
                    f"observed range for {streak} consecutive "
                    f"{'day' if streak == 1 else 'days'}. "
                    "Continue monitoring and follow mission medical protocols."
                )
        else:
            st.warning(
                f"Fewer than {MIN_REFERENCE_ROWS} complete records are available "
                f"for a study-range comparison."
            )


# ==========================================
# TAB 2: HISTORICAL TRENDS
# ==========================================
with tab_history:
    st.subheader("Mission Sleep Trends")
    st.markdown(
        "Explore historical sleep duration by crew member."
    )

    trend_phase_options = [
        phase
        for phase in PHASE_ORDER
        if phase in valid_data["Test_Phase"].unique()
    ]
    if not trend_phase_options:
        trend_phase_options = sorted(valid_data["Test_Phase"].dropna().unique())

    trend_phase = "IN_TEST"
    trend_phase_data = valid_data[valid_data["Test_Phase"] == trend_phase]
    trend_subject_options = sorted(
        trend_phase_data["Subject"].dropna().unique()
    )

    if not trend_subject_options:
        st.warning("No crew members with complete records are available for this phase.")
    else:
        trend_subject = st.selectbox(
            "Select crew member",
            trend_subject_options,
            key="sleep_trend_subject",
        )
        trend_records = (
            trend_phase_data[
                trend_phase_data["Subject"] == trend_subject
            ].sort_values("Date")
        )

        chart_data = trend_records.set_index("Date")[["sleep_hours"]].rename(
            columns={"sleep_hours": "Sleep duration (hours)"}
        )
        phase_values = trend_phase_data["sleep_hours"].dropna()
        if len(phase_values) >= MIN_REFERENCE_ROWS:
            chart_data["Observed 10th percentile"] = phase_values.quantile(0.10)
            chart_data["Observed 90th percentile"] = phase_values.quantile(0.90)

        st.line_chart(chart_data)
        st.markdown("**Historical Records**")
        st.dataframe(
            trend_records[
                [
                    "Date",
                    "BR_Day",
                    "Test_Phase",
                    "sleep_hours",
                    "Sleep Efficiency (%)",
                ]
            ].rename(columns={"sleep_hours": "Sleep duration (hours)"}),
            use_container_width=True,
        )

st.caption(
    "Source: BRSMACT Campaign 1 Actigraphy."
)
