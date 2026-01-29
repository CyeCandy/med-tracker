import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from database import (
    init_db, add_user, get_meds, get_all_patients, 
    get_last_dose_time, add_prescription, get_prescriptions, 
    get_24hr_total, verify_user, add_med_log
)

# Initialize app settings and database
st.set_page_config(page_title="MedLog Shared Care", layout="wide", initial_sidebar_state="expanded")
init_db()

def play_alarm():
    """Plays a notification sound for due medications."""
    components.html('<audio autoplay><source src="https://cdn.pixabay.com/audio/2022/03/15/audio_731477782b.mp3" type="audio/mpeg"></audio>', height=0)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- SIDEBAR: AUTHENTICATION & PATIENT SELECTOR ---
with st.sidebar:
    st.title("🏥 MedLog Pro")
    if not st.session_state.logged_in:
        mode = st.radio("Access", ["Login", "Sign Up"])
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        
        if mode == "Sign Up":
            r = st.selectbox("Role", ["Patient", "Clinician/Carer"])
            if st.button("Create Account"):
                if add_user(u, p, r): 
                    st.success("Account created! Please Sign In.")
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
        st.write(f"**Logged in as:** {st.session_state.user}")
        st.write(f"**Role:** {st.session_state.role}")
        
        # Default view is the user themselves
        target_patient = st.session_state.user
        
        # If user is a Carer, they can select from all patients
        if st.session_state.role == "Clinician/Carer":
            pts = get_all_patients()
            target_patient = st.selectbox("🔍 Managing Patient:", ["-- Select Patient --"] + pts)
        
        st.divider()
        if st.button("Log Out"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.logged_in:
    # Check if Carer has selected a patient
    if st.session_state.role == "Clinician/Carer" and target_patient == "-- Select Patient --":
        st.title("Care Dashboard")
        st.info("Please select a patient from the sidebar to view records or log doses.")
    else:
        st.title(f"Care Record: {target_patient}")
        if st.session_state.role == "Clinician/Carer":
            st.warning(f"⚠️ Viewing and logging as Carer for: **{target_patient}**")

        # 1. SAFETY METRICS
        col1, col2, col3 = st.columns(3)
        o_tot = get_24hr_total(target_patient, "Oxycodone")
        c_tot = get_24hr_total(target_patient, "CBD Oil")
        con_tot = get_24hr_total(target_patient, "Oxycontin")
        
        col1.metric("Oxycodone (24h)", f"{o_tot} ml", "/ 35ml Limit")
        col2.metric("CBD Oil (24h)", f"{c_tot} ml", "/ 4ml Limit")
        col3.metric("Oxycontin (24h)", f"{con_tot} ml")

        # 2. ALERTS LOGIC
        alarm = False
        # (Medication, Safe Interval in Hours)
        check_list = [("Oxycontin", 12), ("Oxycodone", 4)]
        for drug, limit in check_list:
            last = get_last_dose_time(target_patient, drug)
            if last:
                diff = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() / 3600
                if diff >= limit:
                    st.error(f"🔔 {drug} is DUE for {target_patient} ({diff:.1f}h since last dose)")
                    alarm = True
        if alarm: play_alarm()

        # 3. INTERACTIVE TABS: LOGGING & SETUP
        tab1, tab2 = st.tabs(["💊 Log Medication", "⚙️ Care Management"])
        
        with tab1:
            st.subheader("Record New Dose")
            master = get_prescriptions(target_patient)
            if master:
                opts = {f"{n} ({d})": (n, d) for n, d in master}
                sel = st.selectbox("Select Medication:", ["-- Select --"] + list(opts.keys()))
                
                if sel != "-- Select --":
                    n, d = opts[sel]
                    
                    # 24h Cap Safety Check
                    blocked = False
                    if n == "Oxycodone" and o_tot >= 35:
                        st.error("🛑 SAFETY BLOCK: 24h limit (35ml) reached for Oxycodone.")
                        blocked = True
                    
                    if not blocked:
                        if st.button(f"Confirm Dose as {st.session_state.user}"):
                            add_med_log(target_patient, n, d, st.session_state.user)
                            st.success(f"Logged {n} for {target_patient}")
                            st.rerun()
            else:
                st.info("No active prescriptions found. Clinicians/Carers can add them in the Management tab.")

        with tab2:
            if st.session_state.role == "Clinician/Carer":
                st.subheader("Manage Prescriptions")
                new_drug = st.text_input("Drug Name (e.g., Oxycodone)")
                new_dose = st.text_input("Dosage (e.g., 5ml)")
                if st.button("Save/Update Prescription"):
                    if new_drug and new_dose:
                        add_prescription(target_patient, new_drug, new_dose)
                        st.success(f"Prescribed {new_drug} at {new_dose} to {target_patient}")
                        st.rerun()
            else:
                st.info("Prescription management is restricted to Clinicians or Carers.")

        # 4. HISTORY & EXPORT
        st.divider()
        st.subheader(f"📜 {target_patient}'s Log History")
        history_data = get_meds(target_patient)
        
        if history_data: 
            # Columns match the new 'logged_by' database schema
            df = pd.DataFrame(history_data, columns=["Medication", "Dosage", "Time Taken", "Logged By"])
            st.dataframe(df, use_container_width=True)
            
            # CSV Download Feature
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download History as CSV",
                data=csv,
                file_name=f"{target_patient}_med_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
            )
        else:
            st.write("No doses recorded yet.")
else:
    st.title("🏥 Home Care MedLog")
    st.write("Please sign in via the sidebar to access the medication tracker.")