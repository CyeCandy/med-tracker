import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from database import (
    init_db, add_user, get_meds, get_all_patients, 
    get_last_dose_time, add_prescription, get_prescriptions, 
    get_24hr_total, verify_user, add_med_log, set_safety_limit, get_safety_limit
)

CLINIC_KEY = "CARE2026" 

# NICE-style standard max 24h thresholds (approximate for safety logic)
GUIDELINE_MAX = {
    "Oxycodone": 40.0,  # ml/mg total
    "Oxycontin": 80.0,  # mg total
    "CBD Oil": 5.0      # ml total
}

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
            code = st.text_input("Clinic Access Code", type="password") if r != "Patient" else ""
            if st.button("Create Account"):
                if r != "Patient" and code != CLINIC_KEY: st.error("Invalid Clinic Key.")
                elif add_user(u, p, r): st.success("Account created!")
                else: st.error("Username exists.")
        else:
            if st.button("Sign In"):
                res = verify_user(u, p)
                if res:
                    st.session_state.logged_in, st.session_state.user, st.session_state.role = True, u, res[0]
                    st.rerun()
                else: st.error("Invalid Login.")
    else:
        st.write(f"👤 **{st.session_state.user}** ({st.session_state.role})")
        target_patient = st.session_state.user
        if st.session_state.role in ["Clinician", "Carer"]:
            pts = get_all_patients()
            target_patient = st.selectbox("🔍 Select Patient:", ["-- Select Patient --"] + pts)
        if st.button("Log Out"):
            st.session_state.clear()
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.logged_in:
    if st.session_state.role in ["Clinician", "Carer"] and target_patient == "-- Select Patient --":
        st.title("Care Dashboard")
        st.info("Please select a patient.")
    else:
        st.title(f"Care Record: {target_patient}")
        h_all = get_meds(target_patient)

        # 1. Alarms & Safety
        o_tot = get_24hr_total(target_patient, "Oxycodone")
        o_limit = get_safety_limit(target_patient, "Oxycodone") or 35.0 # Default if not set
        
        if o_tot >= o_limit:
            st.error(f"🚨 ALARM: {target_patient} reached 24h cap of {o_limit}ml for Oxycodone!")

        # 2. Tabs
        tab1, tab2 = st.tabs(["💊 Log Dose", "⚙️ Clinician Setup"])
        
        with tab1:
            master = get_prescriptions(target_patient)
            if master:
                opts = {f"{n} ({d})": (n, d) for n, d in master}
                sel = st.selectbox("Medication:", ["-- Select --"] + list(opts.keys()))
                if sel != "-- Select --":
                    n, d = opts[sel]
                    # Logic check against the Clinician's defined cap
                    limit = get_safety_limit(target_patient, n) or 100.0
                    if get_24hr_total(target_patient, n) >= limit:
                        st.error("🛑 DOSE BLOCKED: 24-hour safety limit reached.")
                    elif st.button(f"Confirm Dose"):
                        add_med_log(target_patient, n, d, st.session_state.user)
                        st.success("Logged!"); st.rerun()
            else: st.info("No active prescriptions.")

        with tab2:
            if st.session_state.role == "Clinician":
                st.subheader("🛠️ Prescription & Safety Controls")
                
                # Dynamic Editing Section
                drug_to_edit = st.selectbox("Select Drug to Configure:", ["Oxycodone", "Oxycontin", "CBD Oil"])
                
                col1, col2 = st.columns(2)
                with col1:
                    new_dose = st.text_input(f"Standard Dose for {drug_to_edit}", placeholder="e.g. 5ml")
                with col2:
                    new_cap = st.number_input(f"Max 24h Cap ({drug_to_edit})", min_value=0.0, value=GUIDELINE_MAX.get(drug_to_edit, 10.0))

                # Safety Verification Logic
                guideline = GUIDELINE_MAX.get(drug_to_edit, 999)
                st.divider()
                
                if new_cap > guideline:
                    st.warning(f"⚠️ Warning: This 24h cap ({new_cap}) exceeds standard guidelines ({guideline}).")
                    override = st.checkbox("Confirm Clinical Override (Safety Acknowledge)")
                else:
                    override = True # Within guidelines
                
                if st.button(f"✅ Confirm & Save {drug_to_edit} Change"):
                    if not new_dose:
                        st.error("Please enter a dose amount.")
                    elif not override:
                        st.error("Please check the safety override box for high dosages.")
                    else:
                        add_prescription(target_patient, drug_to_edit, new_dose)
                        set_safety_limit(target_patient, drug_to_edit, new_cap)
                        st.success(f"Prescription updated for {target_patient}")
                        st.rerun()
            else:
                st.warning("🔒 Access Restricted: Clinicians only.")

        # 3. History
        if h_all:
            st.divider()
            st.dataframe(pd.DataFrame(h_all, columns=["Med", "Dose", "Time", "By"]), use_container_width=True)