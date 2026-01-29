import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from database import (
    init_db, add_user, get_meds, get_all_patients, 
    get_last_dose_time, add_prescription, get_prescriptions, 
    get_24hr_total, verify_user, add_med_log
)

st.set_page_config(page_title="MedLog Shared Care", layout="wide")
init_db()

def play_alarm():
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
        st.write(f"**Logged in as:** {st.session_state.user}")
        st.write(f"**Role:** {st.session_state.role}")
        
        target_patient = st.session_state.user
        if st.session_state.role == "Clinician/Carer":
            pts = get_all_patients()
            target_patient = st.selectbox("🔍 Select Patient:", ["-- Select Patient --"] + pts)
        
        st.divider()
        if st.button("Log Out"):
            st.session_state.clear()
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.logged_in:
    if st.session_state.role == "Clinician/Carer" and target_patient == "-- Select Patient --":
        st.title("Care Dashboard")
        st.info("Please select a patient from the sidebar to manage their care.")
    else:
        st.title(f"Care Record: {target_patient}")
        h_all = get_meds(target_patient)

        # 1. Quick Summary (Last 3 Doses)
        st.subheader("⏱️ Recent Activity")
        if h_all:
            recent = h_all[:3]
            cols = st.columns(len(recent))
            for i, (m, d, t, b) in enumerate(recent):
                with cols[i]:
                    st.info(f"**{m}** ({d})\n\n{t}\n\n*By: {b}*")
        else:
            st.write("No doses recorded.")

        # 2. Safety Alarms
        o_tot = get_24hr_total(target_patient, "Oxycodone")
        c_tot = get_24hr_total(target_patient, "CBD Oil")
        
        if o_tot >= 35: st.error(f"🚨 ALARM: Oxycodone 24h limit (35ml) reached! Current: {o_tot}ml")
        if c_tot >= 4: st.error(f"🚨 ALARM: CBD Oil 24h limit (4ml) reached! Current: {c_tot}ml")

        # 3. Trend Chart
        if h_all:
            st.subheader("📊 7-Day Trend")
            df = pd.DataFrame(h_all, columns=["Medication", "Dosage", "Time", "Logged By"])
            df['Time'] = pd.to_datetime(df['Time'])
            df['Date'] = df['Time'].dt.date
            df['Val'] = df['Dosage'].str.extract('(\d+\.?\d*)').astype(float)
            chart_data = df.groupby(['Date', 'Medication'])['Val'].sum().unstack().fillna(0)
            st.bar_chart(chart_data)

        # 4. Due Alerts
        alarm_due = False
        for drug, limit in [("Oxycontin", 12), ("Oxycodone", 4)]:
            last = get_last_dose_time(target_patient, drug)
            if last:
                diff = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() / 3600
                if diff >= limit:
                    st.warning(f"🔔 {drug} is DUE ({diff:.1f}h ago)")
                    alarm_due = True
        if alarm_due: play_alarm()

        # 5. Tabs
        tab1, tab2 = st.tabs(["💊 Log Dose", "⚙️ Prescription Setup"])
        
        with tab1:
            st.subheader("Log Dose")
            master = get_prescriptions(target_patient)
            if master:
                opts = {f"{n} ({d})": (n, d) for n, d in master}
                sel = st.selectbox("Medication:", ["-- Select --"] + list(opts.keys()))
                if sel != "-- Select --":
                    n, d = opts[sel]
                    if n == "Oxycodone" and o_tot >= 35:
                        st.error("🛑 Blocked: Daily limit reached.")
                    elif st.button(f"Confirm Dose as {st.session_state.user}"):
                        add_med_log(target_patient, n, d, st.session_state.user)
                        st.success("Logged!"); st.rerun()

        with tab2:
            if st.session_state.role == "Clinician/Carer":
                st.subheader("Add/Update Prescription")
                nd = st.text_input("Drug Name")
                ds = st.text_input("Dosage (e.g. 5ml)")
                if st.button("Save Prescription"):
                    if nd and ds:
                        add_prescription(target_patient, nd, ds)
                        st.success("Updated!"); st.rerun()
            else:
                st.info("🔒 Restricted: Only Clinician/Carer can modify prescriptions.")

        # 6. History
        st.divider()
        if h_all:
            df_hist = pd.DataFrame(h_all, columns=["Medication", "Dosage", "Time Taken", "Logged By"])
            st.dataframe(df_hist, use_container_width=True)
            csv = df_hist.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download CSV", csv, f"{target_patient}_history.csv", "text/csv")
else:
    st.title("🏥 MedLog Pro")
    st.write("Please sign in to manage care.")