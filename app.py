import streamlit as st
import pandas as pd
import time
import streamlit.components.v1 as components
from datetime import datetime, timedelta
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
                if add_user(u, p, r): st.success("Account created! Please Sign In.")
                else: st.error("Username already exists.")
        else:
            if st.button("Sign In"):
                res = verify_user(u, p)
                if res:
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    st.session_state.role = res[0]
                    st.rerun()
                else: st.error("Invalid credentials.")
    else:
        st.write(f"👤 **User:** {st.session_state.user}")
        st.write(f"🛡️ **Role:** {st.session_state.role}")
        
        target_patient = st.session_state.user
        if st.session_state.role == "Clinician/Carer":
            pts = get_all_patients()
            target_patient = st.selectbox("🔍 Select Patient:", ["-- Select Patient --"] + pts)
        
        st.divider()
        if st.button("Log Out"):
            st.session_state.clear() # Fixes role-merging ghost data
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.logged_in:
    if st.session_state.role == "Clinician/Carer" and target_patient == "-- Select Patient --":
        st.title("Care Dashboard")
        st.info("Please select a patient from the sidebar to begin.")
    else:
        st.title(f"Care Record: {target_patient}")
        h_all = get_meds(target_patient)

        # 1. QUICK SUMMARY
        st.subheader("⏱️ Recent Activity")
        if h_all:
            recent = h_all[:3]
            cols = st.columns(len(recent))
            for i, (m, d, t, b) in enumerate(recent):
                cols[i].info(f"**{m}** ({d})\n\n{t}\n\n*By: {b}*")
        else:
            st.write("No doses recorded yet.")

        # 2. SAFETY ALARMS (24H CAPS)
        st.divider()
        o_tot = get_24hr_total(target_patient, "Oxycodone")
        c_tot = get_24hr_total(target_patient, "CBD Oil")
        
        if o_tot >= 35: st.error(f"🚨 ALARM: Oxycodone 24h limit reached! ({o_tot}ml/35ml)")
        if c_tot >= 4: st.error(f"🚨 ALARM: CBD Oil 24h limit reached! ({c_tot}ml/4ml)")

        # 3. REAL-TIME COUNTDOWN TIMERS
        st.subheader("⏲️ Next Dose Countdowns")
        timers = [("Oxycontin", 12), ("Oxycodone", 4)]
        t_cols = st.columns(len(timers))
        alarm_trigger = False

        for idx, (drug, interval) in enumerate(timers):
            last_time_str = get_last_dose_time(target_patient, drug)
            with t_cols[idx]:
                if last_time_str:
                    last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M")
                    next_due = last_time + timedelta(hours=interval)
                    remaining = next_due - datetime.now()
                    
                    if remaining.total_seconds() > 0:
                        st.metric(f"Next {drug}", f"{str(remaining).split('.')[0]} left")
                    else:
                        st.warning(f"🔔 {drug} is DUE NOW")
                        st.write(f"Overdue by: {str(abs(remaining)).split('.')[0]}")
                        alarm_trigger = True
                else:
                    st.write(f"No {drug} history.")

        if alarm_trigger: play_alarm()

        # 4. TREND CHART
        if h_all:
            st.subheader("📊 7-Day Trend")
            df = pd.DataFrame(h_all, columns=["Medication", "Dosage", "Time", "Logged By"])
            df['Time'] = pd.to_datetime(df['Time'])
            df['Date'] = df['Time'].dt.date
            df['Val'] = df['Dosage'].str.extract('(\d+\.?\d*)').astype(float)
            chart_data = df.groupby(['Date', 'Medication'])['Val'].sum().unstack().fillna(0)
            st.bar_chart(chart_data)

        # 5. DOSING & CLINICIAN TABS
        tab1, tab2 = st.tabs(["💊 Log Medication", "⚙️ Clinician Setup"])
        
        with tab1:
            st.subheader("Record Administration")
            master = get_prescriptions(target_patient)
            if master:
                opts = {f"{n} ({d})": (n, d) for n, d in master}
                sel = st.selectbox("Choose Medication:", ["-- Select --"] + list(opts.keys()))
                if sel != "-- Select --":
                    n, d = opts[sel]
                    # Block Oxycodone if over 35ml
                    if n == "Oxycodone" and o_tot >= 35:
                        st.error("🛑 ACTION BLOCKED: Safety limit reached.")
                    elif st.button(f"Confirm Dose as {st.session_state.user}"):
                        add_med_log(target_patient, n, d, st.session_state.user)
                        st.success("Dose logged successfully.")
                        st.rerun()
            else:
                st.info("No active prescriptions.")

        with tab2:
            if st.session_state.role == "Clinician/Carer":
                st.subheader("Manage Master Prescription List")
                nd = st.text_input("New Drug Name")
                ds = st.text_input("Dosage Amount (e.g. 5ml)")
                if st.button("Save to Patient File"):
                    if nd and ds:
                        add_prescription(target_patient, nd, ds)
                        st.success(f"Prescription saved for {target_patient}")
                        st.rerun()
            else:
                st.warning("🔒 Access Restricted: Only Clinicians/Carers can manage drugs.")

        # 6. EXPORT
        st.divider()
        if h_all:
            csv = pd.DataFrame(h_all, columns=["Med", "Dose", "Time", "By"]).to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download History CSV", csv, f"{target_patient}_med_log.csv", "text/csv")
else:
    st.title("🏥 Home Care MedLog")
    st.write("Please sign in to access the care portal.")