import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from database import (
    init_db, add_user, get_meds, get_all_patients, 
    get_last_dose_time, add_prescription, get_prescriptions, 
    get_24hr_total, verify_user, add_med_log
)

# Initialize app and DB
st.set_page_config(page_title="MedLog Shared Care", layout="wide", initial_sidebar_state="expanded")
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
            r = st.selectbox("Role", ["Patient", "Clinician"])
            if st.button("Create Account"):
                if add_user(u, p, r): 
                    st.success("Account created! Please Login.")
                else:
                    st.error("Username already exists.")
        else:
            if st.button("Sign In"):
                res = verify_user(u, p)
                if res:
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    st.session_state.role = res[0]
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    else:
        st.write(f"**User:** {st.session_state.user} ({st.session_state.role})")
        
        target_patient = st.session_state.user
        if st.session_state.role == "Clinician":
            pts = get_all_patients()
            target_patient = st.selectbox("🔍 Managing Patient:", ["-- Select Patient --"] + pts)
        
        st.divider()
        if st.button("Log Out"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.logged_in:
    # Logic fix for Line 62 area
    if st.session_state.role == "Clinician" and target_patient == "-- Select Patient --":
        st.title("Clinician Dashboard")
        st.info("Please select a patient from the sidebar to manage their care.")
    else:
        st.title(f"Care Record: {target_patient}")
        if st.session_state.role == "Clinician":
            st.warning(f"⚠️ Viewing and logging for **{target_patient}**")

        # 1. Metrics
        col1, col2, col3 = st.columns(3)
        o_tot = get_24hr_total(target_patient, "Oxycodone")
        c_tot = get_24hr_total(target_patient, "CBD Oil")
        con_tot = get_24hr_total(target_patient, "Oxycontin")
        
        col1.metric("Oxycodone (24h)", f"{o_tot} ml", "Limit: 35ml")
        col2.metric("CBD Oil (24h)", f"{c_tot} ml", "Limit: 4ml")
        col3.metric("Oxycontin (24h)", f"{con_tot} ml")

        # 2. Alerts
        alarm = False
        for drug, limit in [("Oxycontin", 12), ("Oxycodone", 4)]:
            last = get_last_dose_time(target_patient, drug)
            if last:
                diff = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() / 3600
                if diff >= limit:
                    st.error(f"🔔 {drug} is DUE for {target_patient} ({diff:.1f}h ago)")
                    alarm = True
        if alarm: play_alarm()

        # 3. Recording & Setup Tabs
        tab1, tab2 = st.tabs(["💊 Log Dose", "⚙️ Patient Management"])
        
        with tab1:
            st.subheader("Record New Dose")
            master = get_prescriptions(target_patient)
            if master:
                opts = {f"{n} ({d})": (n, d) for n, d in master}
                sel = st.selectbox("Select Medication:", ["-- Select --"] + list(opts.keys()))
                if sel != "-- Select --":
                    n, d = opts[sel]
                    if n == "Oxycodone" and o_tot >= 35:
                        st.error("🛑 Blocked: 24h limit reached.")
                    elif st.button(f"Confirm Dose as {st.session_state.user}"):
                        add_med_log(target_patient, n, d, st.session_state.user)
                        st.success(f"Logged {n} for {target_patient}")
                        st.rerun()
            else:
                st.info("No medications prescribed for this patient.")

        with tab2:
            if st.session_state.role == "Clinician":
                st.subheader("Add New Prescription")
                new_drug = st.text_input("Drug Name")
                new_dose = st.text_input("Dosage (e.g., 5ml)")
                if st.button("Save Prescription"):
                    if new_drug and new_dose:
                        add_prescription(target_patient, new_drug, new_dose)
                        st.success(f"Prescribed {new_drug} to {target_patient}")
                        st.rerun()
            else:
                st.info("Prescription settings are only available to Clinicians.")

        # 4. History
        st.subheader(f"📜 {target_patient}'s History")
        h = get_meds(target_patient)
        if h: 
            df = pd.DataFrame(h, columns=["Medication", "Dosage", "Time Taken", "Logged By"])
            st.dataframe(df, use_container_width=True)
        else:
            st.write("No doses logged yet.")
else:
    st.title("🏥 Home Care MedLog")
    st.write("Please use the side panel to sign in.")