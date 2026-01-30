import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from database import (
    init_db, add_user, get_meds, get_all_patients, 
    get_last_dose_time, add_prescription, get_prescriptions, 
    get_24hr_total, verify_user, add_med_log
)

CLINIC_KEY = "CARE2026" 

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
            r = st.selectbox("Role", ["Patient", "Clinician", "Carer"])
            access_code = ""
            if r in ["Clinician", "Carer"]:
                access_code = st.text_input("Clinic Access Code", type="password")
            if st.button("Create Account"):
                if r in ["Clinician", "Carer"] and access_code != CLINIC_KEY:
                    st.error("Invalid Clinic Access Code.")
                elif add_user(u, p, r): st.success(f"Account created as {r}!")
                else: st.error("Username already exists.")
        else:
            if st.button("Sign In"):
                res = verify_user(u, p)
                if res:
                    st.session_state.logged_in, st.session_state.user, st.session_state.role = True, u, res[0]
                    st.rerun()
                else: st.error("Invalid Login.")
    else:
        st.write(f"👤 **User:** {st.session_state.user} | **Role:** {st.session_state.role}")
        target_patient = st.session_state.user
        is_admin = st.session_state.role in ["Clinician", "Carer"]
        if is_admin:
            pts = get_all_patients()
            target_patient = st.selectbox("🔍 Select Patient:", ["-- Select Patient --"] + pts)
        if st.button("Log Out"):
            st.session_state.clear()
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.logged_in:
    is_admin = st.session_state.role in ["Clinician", "Carer"]
    if is_admin and target_patient == "-- Select Patient --":
        st.title("Care Dashboard")
        st.info("Please select a patient from the sidebar.")
    else:
        st.title(f"Care Record: {target_patient}")
        h_all = get_meds(target_patient)

        # 1. Quick Summary
        st.subheader("⏱️ Recent Activity")
        if h_all:
            recent = h_all[:3]
            cols = st.columns(len(recent))
            for i, (m, d, t, b) in enumerate(recent):
                cols[i].info(f"**{m}** ({d})\n\n{t}\n\n*By: {b}*")

        # 2. Safety Alarms
        o_tot = get_24hr_total(target_patient, "Oxycodone")
        c_tot = get_24hr_total(target_patient, "CBD Oil")
        if o_tot >= 35: st.error(f"🚨 ALARM: Oxycodone limit reached! ({o_tot}ml)")
        if c_tot >= 4: st.error(f"🚨 ALARM: CBD Oil limit reached! ({c_tot}ml)")

        # 3. Timers
        st.subheader("⏲️ Next Dose Countdown")
        timers = [("Oxycontin", 12), ("Oxycodone", 4)]
        t_cols = st.columns(2)
        alarm_trigger = False
        for idx, (drug, interval) in enumerate(timers):
            last_time_str = get_last_dose_time(target_patient, drug)
            with t_cols[idx]:
                if last_time_str:
                    last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M")
                    next_due = last_time + timedelta(hours=interval)
                    rem = next_due - datetime.now()
                    if rem.total_seconds() > 0: st.metric(f"Next {drug}", f"{str(rem).split('.')[0]} left")
                    else:
                        st.warning(f"🔔 {drug} DUE NOW")
                        alarm_trigger = True
                else: st.write(f"No {drug} history.")
        if alarm_trigger: play_alarm()

        # 4. Tabs
        tab1, tab2 = st.tabs(["💊 Log Dose", "⚙️ Setup"])
        with tab1:
            master = get_prescriptions(target_patient)
            if master:
                opts = {f"{n} ({d})": (n, d) for n, d in master}
                sel = st.selectbox("Select Medication:", ["-- Select --"] + list(opts.keys()))
                if sel != "-- Select --":
                    n, d = opts[sel]
                    if n == "Oxycodone" and o_tot >= 35: st.error("🛑 Daily limit reached.")
                    elif st.button(f"Confirm Dose as {st.session_state.user}"):
                        add_med_log(target_patient, n, d, st.session_state.user)
                        st.success("Logged!"); st.rerun()
            else: st.info("No prescriptions set.")

        with tab2:
            if st.session_state.role == "Clinician":
                st.subheader("📋 Prescription Management")
                st.write(f"Define standard doses for **{target_patient}**")
                
                # Standard Drugs Quick-Entry
                col1, col2, col3 = st.columns(3)
                with col1:
                    oxyc_d = st.text_input("Oxycontin Dose", "10mg")
                    if st.button("Set Oxycontin"): add_prescription(target_patient, "Oxycontin", oxyc_d); st.rerun()
                with col2:
                    oxy_d = st.text_input("Oxycodone Dose", "5ml")
                    if st.button("Set Oxycodone"): add_prescription(target_patient, "Oxycodone", oxy_d); st.rerun()
                with col3:
                    cbd_d = st.text_input("CBD Oil Dose", "0.5ml")
                    if st.button("Set CBD Oil"): add_prescription(target_patient, "CBD Oil", cbd_d); st.rerun()
                
                st.divider()
                st.write("Other Medication:")
                custom_n = st.text_input("Drug Name")
                custom_d = st.text_input("Dosage")
                if st.button("Save Custom Medication"):
                    if custom_n and custom_d: add_prescription(target_patient, custom_n, custom_d); st.rerun()
            else:
                st.info("🛡️ Restricted: Only a Clinician can set dosages.")

        # 5. History & Trends
        if h_all:
            st.divider()
            st.subheader("📊 History & Trends")
            df = pd.DataFrame(h_all, columns=["Med", "Dose", "Time", "By"])
            st.dataframe(df, use_container_width=True)