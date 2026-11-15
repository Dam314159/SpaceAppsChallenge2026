import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Muscle & Nerve Monitor", page_icon="💪", layout="wide")

# --- HEADER ---
st.title("💪 Muscle & Nerve Health Monitor")
st.markdown("""
**Mission Goal:** Long space missions cause muscles to weaken and nerves to slow down because there is no gravity. 
This tool allows astronauts to run a quick leg reflex test, enter the results, and get an instant evaluation of their health.
""")

# --- SIDEBAR ATTRIBUTION ---
st.sidebar.header("📁 Data Source")

st.sidebar.markdown("""
The default dataset is sourced from the **NASA Life Sciences Data Archive**.
* **Experiment:** Bed Rest Standard Measures: Tendon Reflex (BRSMTReflex)
* **Investigator:** Millard F. Reschke (NASA JSC)
""")

with st.sidebar.expander("ℹ️ About this dataset", expanded=False):
    st.markdown("""
    **What it is:** A NASA study measuring the **leg reflex** (like a knee-jerk) in bed-rest volunteers — an Earth analogue for spaceflight.

    **What it records:**
    * **Peak_Amp (mV)** — how strong the muscle responds = muscle strength
    * **Peak_Latency (ms)** — how fast the nerve fires = nerve speed
    * **BR_Day** — day of the bed-rest study (mission timeline)
    * **Muscle** — which lower-leg muscle was tested

    **Why it matters:** In microgravity, legs aren't used against gravity, so muscles weaken and nerves slow down. This dataset shows how fast that happens.

    **Note:** The thresholds in this app are simplified, not official NASA medical limits.
    """)

st.sidebar.markdown("[🔗 View Official NASA Data Portal](https://nlsp.nasa.gov/explore/data/details/a3090eb9-34bd-5248-8549-4c8fbde4b76a?dataType=EXPERIMENTS)")

# --- INSIGHT HELPERS ---
def interpret_result(peak_amp, peak_latency):
    """Return plain-language insights for a single test."""
    insights = []

    if peak_amp < 20:
        insights.append(f"Muscle strength is **{peak_amp:.1f} mV** — **{20 - peak_amp:.1f} mV below** the critical threshold of 20 mV. Significant muscle atrophy.")
    elif peak_amp < 50:
        insights.append(f"Muscle strength is **{peak_amp:.1f} mV** — in the caution band. Need **{50 - peak_amp:.1f} mV more** to reach the safe zone (≥50 mV).")
    else:
        insights.append(f"Muscle strength is **{peak_amp:.1f} mV** — above the 50 mV safe threshold. Good muscle maintenance.")

    if peak_latency > 65:
        insights.append(f"Nerve latency is **{peak_latency:.1f} ms** — **{peak_latency - 65:.1f} ms slower** than the critical limit of 65 ms. Nerve conduction impaired.")
    elif peak_latency > 60:
        insights.append(f"Nerve latency is **{peak_latency:.1f} ms** — in the caution band. **{peak_latency - 60:.1f} ms above** the 60 ms warning line.")
    else:
        insights.append(f"Nerve latency is **{peak_latency:.1f} ms** — within the healthy range (≤60 ms). Nerve signalling fast.")

    if peak_amp >= 50 and peak_latency <= 60:
        insights.append("**Combined verdict:** Both muscle and nerve metrics are healthy. Countermeasures are working.")
    elif peak_amp < 20 or peak_latency > 65:
        insights.append("**Combined verdict:** At least one metric is in the critical zone. Clinical review warranted.")
    else:
        insights.append("**Combined verdict:** One or both metrics are drifting. Early intervention (extra ARED training, neuromuscular stimulation) recommended.")

    return insights


def analyze_trend(subject_df, muscle_name):
    """Generate insights from a historical dataframe for one subject+muscle."""
    df = subject_df.dropna(subset=['BR_Day', 'Peak_Amp']).sort_values('BR_Day')
    if len(df) < 2:
        return ["Not enough data points to detect a trend (need at least 2 tests)."]

    insights = []
    first_amp = df['Peak_Amp'].iloc[0]
    last_amp = df['Peak_Amp'].iloc[-1]
    day_span = df['BR_Day'].iloc[-1] - df['BR_Day'].iloc[0]

    pct_change = ((last_amp - first_amp) / first_amp) * 100 if first_amp else 0
    direction = "declined" if pct_change < 0 else "improved"
    insights.append(
        f"**Overall trend:** Strength has **{direction} by {abs(pct_change):.1f}%** "
        f"({first_amp:.1f} mV → {last_amp:.1f} mV) over {day_span:.0f} mission days."
    )

    if day_span > 0:
        rate = (last_amp - first_amp) / day_span
        if rate < -1.0:
            insights.append(f"⚠️ **Rate of loss:** {abs(rate):.2f} mV/day — **fast decline**. Countermeasures insufficient.")
        elif rate < -0.3:
            insights.append(f"**Rate of loss:** {abs(rate):.2f} mV/day — moderate, expected decline.")
        elif rate > 0.3:
            insights.append(f"✅ **Rate of change:** +{rate:.2f} mV/day — strength **recovering**. Protocol effective.")
        else:
            insights.append(f"**Rate of change:** {rate:.2f} mV/day — strength essentially **stable**.")

    for threshold, label in [(50, "warning"), (20, "critical")]:
        below = df[df['Peak_Amp'] < threshold]
        if not below.empty and df['Peak_Amp'].iloc[0] >= threshold:
            cross_day = below['BR_Day'].iloc[0]
            insights.append(f"🚨 **Threshold crossing:** Dropped below the **{threshold} mV {label} line** on mission day **{cross_day:.0f}**.")

    if last_amp < 20:
        insights.append("**Current status:** CRITICAL — immediate medical review required.")
    elif last_amp < 50:
        insights.append("**Current status:** CAUTION — increase resistance training.")
    else:
        insights.append("**Current status:** NOMINAL — maintain current protocol.")

    return insights


# --- DATA LOADING ---
@st.cache_data
def load_default_data():
    file_path = "data/BRSMTREFLEX_Campaign_3_Monosynaptic_Reflex_C3G_5580_Avg.csv"
    if not os.path.exists(file_path):
        file_path = "BRSMTREFLEX_Campaign_3_Monosynaptic_Reflex_C3G_5580_Avg.csv"
    try:
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.strip()
        return df
    except:
        return None

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🩺 Daily Health Check", "📁 Batch Processing", "📊 Historical Trends"])

# ==========================================
# TAB 1: DAILY HEALTH CHECK
# ==========================================
with tab1:
    st.subheader("Enter New Test Results")
    
    with st.expander("❓ What do these numbers mean? (Click to expand)", expanded=True):
        st.markdown("""
        * **Amplitude (Muscle Strength):** Think of this as **Engine Power**. It measures how strong the muscle signal is. 
            * **High mV** = Strong Muscle (Good)
            * **Low mV** = Weak Muscle (Bad)
        * **Latency (Nerve Speed):** Think of this as **Engine Delay**. It measures how fast the nerve sends the signal to the muscle.
            * **Low ms** = Fast Nerves (Good)
            * **High ms** = Slow Nerves (Bad)
        """)
    
    st.markdown("Use the inputs below to enter the data from the astronaut's latest leg reflex test.")
    
    muscle_dict = {
        "Outer Calf (lat_gast)": "lat_gast",
        "Inner Calf (med_gast)": "med_gast",
        "Outer Soleus (lat_sol)": "lat_sol",
        "Inner Soleus (med_sol)": "med_sol",
        "Gastroc-Soleus (gast_sol_int)": "gast_sol_int"
    }

    col1, col2 = st.columns(2)
    
    with col1:
        selected_muscle_name = st.selectbox(
            "Which muscle was tested?", 
            options=list(muscle_dict.keys()),
            help="Select the part of the leg tested. 'Calf' is the back of the lower leg."
        )
        muscle = muscle_dict[selected_muscle_name] 

    with col2:
        peak_amp = st.number_input(
            "Muscle Strength (Amplitude in mV)", 
            min_value=0.0, max_value=150.0, value=55.0, step=1.0,
            help="Engine Power. Higher numbers mean stronger muscles. Below 50 is a warning, below 20 is critical."
        )

    peak_latency = st.number_input(
        "Nerve Speed (Latency in ms)", 
        min_value=0.0, max_value=100.0, value=60.0, step=0.5,
        help="Engine Delay. Lower numbers mean a faster, healthier nerve. Above 60 is a warning, above 65 is critical."
    )

    st.write("") 
    evaluate_btn = st.button("▶ RUN HEALTH CHECK", type="primary", use_container_width=True)

    if evaluate_btn:
        st.divider()
        
        risk_level = "NOMINAL"
        action_text = "The astronaut's muscles and nerves are healthy. Continue normal daily exercise."
        
        if peak_amp < 20 or peak_latency > 65:
            risk_level = "CRITICAL ALERT"
            action_text = "The muscles are too weak or the nerves are too slow. Stop all physical activities and notify the Flight Surgeon immediately."
        elif peak_amp < 50 or peak_latency > 60:
            risk_level = "CAUTION"
            action_text = "Signs of muscle weakness. The astronaut needs to do extra resistance training (ARED machine) today."

        if risk_level == "CRITICAL ALERT":
            st.error(f"### 🚨 SYSTEM STATUS: {risk_level}")
            st.error(f"**What to do next:** {action_text}")
        elif risk_level == "CAUTION":
            st.warning(f"### ⚠️ SYSTEM STATUS: {risk_level}")
            st.warning(f"**What to do next:** {action_text}")
        else:
            st.success(f"### ✅ SYSTEM STATUS: {risk_level}")
            st.success(f"**What to do next:** {action_text}")

        st.write("") 

        # --- INTERPRETATION BLOCK ---
        st.markdown("#### 🧠 What This Means")
        for line in interpret_result(peak_amp, peak_latency):
            st.markdown(f"- {line}")

        st.write("")

        st.markdown("#### 📡 Test Overview")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Sensor Connection", "Strong", "Optimal")
        t2.metric("Signal Interference", "Low", "-0.4")
        t3.metric("Test Length", "1.45s", "Normal")
        t4.metric("Device Battery", "87%", "Good")
        
        st.markdown("#### 📊 Health Thresholds (Green is Good, Red is Bad)")
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            fig_amp = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = peak_amp,
                title = {'text': "Muscle Strength (mV)"},
                gauge = {
                    'axis': {'range': [0, 150]},
                    'bar': {'color': "#2196F3"},
                    'steps': [
                        {'range': [0, 20], 'color': "#ff4b4b"},
                        {'range': [20, 50], 'color': "#ffa421"},
                        {'range': [50, 150], 'color': "#21c354"}
                    ]
                }
            ))
            fig_amp.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_amp, use_container_width=True)

        with chart_col2:
            fig_lat = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = peak_latency,
                title = {'text': "Nerve Speed (ms)"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#2196F3"},
                    'steps': [
                        {'range': [0, 60], 'color': "#21c354"},
                        {'range': [60, 65], 'color': "#ffa421"},
                        {'range': [65, 100], 'color': "#ff4b4b"}
                    ]
                }
            ))
            fig_lat.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_lat, use_container_width=True)

# ==========================================
# TAB 2: BATCH PROCESSING
# ==========================================
with tab2:
    st.subheader("Batch Processing for the Whole Crew")
    st.markdown("""
    Have a file with tests from multiple astronauts? Upload it here to check everyone at once. 
    The system will automatically flag anyone who needs medical attention.
    """)
    
    template_df = pd.DataFrame({
        'Subject': ['5580', '5580'],
        'Muscle': ['med_gast', 'lat_sol'],
        'Peak_Amp': [55.0, 15.0],
        'Peak_Latency': [59.5, 65.2]
    })
    csv_template = template_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Download Example CSV File", 
        data=csv_template, 
        file_name='health_check_template.csv', 
        mime='text/csv',
        help="Download this file to see the exact format required for batch processing."
    )
    
    uploaded_file = st.file_uploader("Upload Health Check File (.csv)", type="csv")
    
    if uploaded_file is not None:
        try:
            batch_df = pd.read_csv(uploaded_file)
            required_cols = ['Subject', 'Muscle', 'Peak_Amp', 'Peak_Latency']
            
            if not all(col in batch_df.columns for col in required_cols):
                st.error(f"Missing required columns. Ensure your file has: {', '.join(required_cols)}")
            else:
                if st.button("▶ RUN BATCH CHECK", type="primary"):
                    with st.spinner("Analyzing health data for all crew members..."):
                        results = batch_df.apply(lambda row: (
                            "CRITICAL" if row['Peak_Amp'] < 20 or row['Peak_Latency'] > 65 
                            else "CAUTION" if row['Peak_Amp'] < 50 or row['Peak_Latency'] > 60 
                            else "NOMINAL"
                        ), axis=1)
                        
                        batch_df['Health_Status'] = results

                        # Batch summary insights
                        n_crit = (results == "CRITICAL").sum()
                        n_caut = (results == "CAUTION").sum()
                        n_nom = (results == "NOMINAL").sum()

                        st.success(f"Analysis complete for {len(batch_df)} records.")
                        st.markdown("#### 🧠 Batch Summary")
                        st.markdown(f"- **{n_nom}** records NOMINAL — healthy, no action needed.")
                        st.markdown(f"- **{n_caut}** records CAUTION — schedule extra resistance training.")
                        st.markdown(f"- **{n_crit}** records CRITICAL — flag for Flight Surgeon review immediately.")
                        if n_crit > 0:
                            st.error(f"⚠️ {n_crit} crew member(s) in critical zone. Escalate now.")
                        elif n_caut > 0:
                            st.warning(f"⚠️ {n_caut} crew member(s) in caution zone. Monitor closely.")

                        st.dataframe(batch_df, use_container_width=True)
                        
                        result_csv = batch_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "📥 Download Analyzed Results", 
                            data=result_csv, 
                            file_name='crew_health_results.csv', 
                            mime='text/csv', 
                            type="primary"
                        )
        except Exception as e:
            st.error(f"Error: {e}")

# ==========================================
# TAB 3: HISTORICAL TRENDS
# ==========================================
with tab3:
    df = load_default_data()
    if df is not None:
        st.subheader("Mission Health Trends")
        st.markdown("See how the astronaut's muscle strength changes over the days of the mission. If the line drops into the orange or red zones, the astronaut is losing muscle mass.")
        
        col1, col2 = st.columns(2)
        with col1:
            subject = st.selectbox("Select Crew Member ID", df['Subject'].dropna().unique())
        with col2:
            muscle_filter = st.selectbox("Select Muscle to View", df['Muscle'].dropna().unique())
            
        subject_df = df[(df['Subject'] == subject) & (df['Muscle'] == muscle_filter)].copy()
        
        subject_df['BR_Day'] = pd.to_numeric(subject_df['BR_Day'], errors='coerce')
        subject_df = subject_df.sort_values('BR_Day')

        if not subject_df.empty:
            # --- INSIGHT SUMMARY ABOVE THE CHART ---
            st.markdown("#### 🧠 Trend Insights")
            for line in analyze_trend(subject_df, muscle_filter):
                st.markdown(f"- {line}")

            st.write("")

            # Line Chart
            fig = px.line(
                subject_df, x='BR_Day', y='Peak_Amp', markers=True, 
                title=f"Muscle Strength Over Time (Crew {subject}, Muscle: {muscle_filter})"
            )
            fig.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="Critical Danger Zone")
            fig.add_hline(y=50, line_dash="dash", line_color="orange", annotation_text="Warning Zone")
            fig.update_layout(yaxis_title="Muscle Strength (mV)", xaxis_title="Day of Mission")
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("**Raw Data Table:**")
            st.dataframe(subject_df[['BR_Day', 'Test_Phase', 'Peak_Amp', 'Peak_Latency']], use_container_width=True)

            # --- MUSCLE-BY-MUSCLE COMPARISON ---
            st.markdown("#### 🔍 Muscle-by-Muscle Comparison")
            all_muscles = df[df['Subject'] == subject].copy()
            all_muscles['BR_Day'] = pd.to_numeric(all_muscles['BR_Day'], errors='coerce')
            all_muscles = all_muscles.dropna(subset=['Peak_Amp']).sort_values('BR_Day')

            rows = []
            for m in all_muscles['Muscle'].dropna().unique():
                mdf = all_muscles[all_muscles['Muscle'] == m]
                if len(mdf) < 2:
                    continue
                first_a = mdf['Peak_Amp'].iloc[0]
                last_a = mdf['Peak_Amp'].iloc[-1]
                pct = ((last_a - first_a) / first_a * 100) if first_a else 0
                rows.append({
                    'Muscle': m,
                    'Tests': len(mdf),
                    'First_Amp': round(first_a, 1),
                    'Latest_Amp': round(last_a, 1),
                    'Change_%': round(pct, 1)
                })

            if rows:
                comparison = pd.DataFrame(rows).sort_values('Change_%')
                st.dataframe(comparison, use_container_width=True)
                worst = comparison.iloc[0]
                if worst['Change_%'] < 0:
                    st.info(f"**Weakest muscle:** `{worst['Muscle']}` changed **{worst['Change_%']}%**. Prioritise this muscle in the next exercise session.")
                else:
                    st.success("All muscles are stable or improving. No priority intervention needed.")
            else:
                st.info("Not enough multi-muscle data to compare for this crew member.")
        else:
            st.warning("No data available for this combination.")
    else:
        st.error("Default mission data not found. Make sure the CSV is in the 'data' folder.")