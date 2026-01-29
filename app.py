import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from database import (
    init_db, add_user, get_meds, get_all_patients, 
    get_last_dose_time, add_prescription, get_prescriptions, 
    get_24hr_total, verify_user, add_med_log
)

# Initialize app
st.set_page_config(page_title="MedLog Shared Care", layout="wide", initial_sidebar_state="expanded")
init_db()

def play_alarm():
    """Plays a notification sound for due medications."""
    components.html('<audio autoplay><source src="https://cdn.pixabay.com/audio/2022/03/15/audio_731477782b.mp3" type="audio/mpeg"></audio>', height=0)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- SIDEBAR ---
with st.sidebar:
    st.title("🏥 MedLog Pro")
    if not st.session_state.logged_in:
        mode = st.radio("Access", ["Login", "Sign Up"])
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if mode == "Sign Up":
            r = st.selectbox("Role", ["Patient", "Clinician/Carer"])
            if st.button("Create Account"):
                if add_user(u, p, r): st.success("Created! Please Sign In.")
                else: st.error("Username taken.")
        else:
            if st.button("Sign In"):
                res = verify_user(u, p)
                if res:
                    st.session_state.logged_in, st.session_state.user, st.session_state.role = True, u, res[0]
                    st.rerun()
                else: st.error("Invalid Login.")
    else:
        st.write(f"**User:** {st.session_state.user} ({st.session_state.role})")
        target_patient = st.session_state.user
        if st.session_state.role == "Clinician/Carer":
            pts = get_all_patients()
            target_patient = st.selectbox("🔍 Managing Patient:", ["-- Select Patient --"] + pts)
        
        st.divider()
        if st.button("Log Out"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.logged_in:
    if st.session_state.role == "Clinician/Carer" and target_patient == "-- Select Patient --":
        st.title("Care Dashboard")
        st.info("Please select a patient from the sidebar to begin.")
    else:
        st.title(f"Care Record: {target_patient}")
        
        # Pull history once for multiple uses
        h_all = get_meds(target_patient)

        # 1. QUICK SUMMARY (LAST 3 DOSES)
        st.subheader("⏱️ Recent Activity")
        if h_all:
            recent = h_all[:3]
            cols = st.columns(len(recent))
            for i, (m, d, t, b) in enumerate(recent):
                with cols[i]:
                    st.info(f"**{m}** ({d})\n\n{t}\n\n*By: {b}*")
        else:
            st.write("No recent activity found.")

        # 2. METRICS & 24H ALARMS
        st.divider()
        col1, col2, col3 = st.columns(3)
        o_tot = get_24hr_total(target_patient, "Oxycodone")
        c_tot = get_24hr_total(target_patient, "CBD Oil")
        con_tot = get_24hr_total(target_patient, "Oxycontin")

        # Visual Alarms for 24h Limits
        if o_tot >= 35: st.error(f"🚨 ALARM: Oxycodone 24h limit (35ml) REACHED: {o_tot}ml")
        if c_tot >= 4: st.error(f"🚨 ALARM: CBD Oil 24h limit (4ml) REACHED: {c_tot}ml")

        col1.metric("Oxycodone (24h)", f"{o_tot} ml", "/ 35ml")
        col2.metric("CBD Oil (24h)", f"{c_tot} ml", "/ 4ml")
        col3.metric("Oxycontin (24h)", f"{con_tot} ml")

        # 3. TREND CHART (Last 7 Days)
        if h_all:
            st.subheader("📊 7-Day Dosage Trend")
            df_chart = pd.DataFrame(h_all, columns=["Medication", "Dosage", "Time", "Logged By"])
            df_chart['Time'] = pd.to_datetime(df_chart['Time'])
            df_chart['Date'] = df_chart['Time'].dt.date
            # Extraction logic for charts (handles '5ml', '2.5 ml', etc)
            df_chart['Dosage_Val'] = df_chart['Dosage'].str.extract('(\d+\.?\d*)').astype(float)
            
            chart_pivot = df_chart.groupby(['Date', 'Medication'])['Dosage_Val'].sum().unstack().fillna(0)
            st.bar_chart(chart_pivot)

        # 4. DUE ALERTS
        alarm = False
        for drug, limit in [("Oxycontin", 12), ("Oxycodone", 4)]:
            last = get_last_dose_time(target_patient, drug)
            if last:
                diff = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() / 3600
                if diff >= limit:
                    st.warning(f"🔔 {drug} is DUE ({diff:.1f}h since last dose)"); alarm = True
        if alarm: play_alarm()

        # 5. RECORDING & MANAGEMENT
        tab1, tab2 = st.tabs(["💊 Log Dose", "⚙️ Prescriptions"])
        with tab1:
            st.subheader("Record New Dose")
            master = get_prescriptions(target_patient)
            if master:
                opts = {f"{n} ({d})": (n, d) for n, d in master}
                sel = st.selectbox("Select Medication:", [""] + list(opts.keys()))
                if sel:
                    n, d = opts[sel]
                    if n == "Oxycodone" and o_tot >= 35:
                        st.error("🛑 Safety Block: 24h limit reached.")
                    elif st.button(f"Confirm Dose as {st.session_state.user}"):
                        add_med_log(target_patient, n, d, st.session_state.user)
                        st.success(f"Logged {n}"); st.rerun()
            else: st.info("No active prescriptions.")

        with tab2:
            if st.session_state.role == "Clinician/Carer":
                st.subheader("Manage Prescriptions")
                nd = st.text_input("Drug Name")