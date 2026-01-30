import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import *

CLINIC_KEY = "CARE2026" 

# NICE-style standard max 24h thresholds (Approximate for software logic)
GUIDELINE_MAX = {
    "Oxycodone": 40.0,
    "Oxycontin": 80.0,
    "CBD Oil": 5.0
}

st.set_page_config(page_title="MedLog Shared Care", layout="wide")
init_db()

def play_alarm():
    st.components.v1.html('<audio autoplay><source src="https://cdn.pixabay.com/audio/2022/03/15/audio_731477782b.mp3" type="audio/mpeg"></audio>', height=0)

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
                elif add_user(u, p, r): st.success("Created!")
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

        # 1. Safety Total Check
        st.subheader("⚠️ Safety Status")
        for drug in ["Oxycodone", "Oxycontin", "CBD Oil"]:
            curr = get_24hr_total(target_patient, drug)
            limit = get_safety_limit(target_patient, drug) or 100.0
            if curr >= limit:
                st.error(f"🚨 {drug} 24h limit reached! ({curr}/{limit})")

        # 2. Tabs
        tab1, tab2, tab3 = st.tabs(["💊 Log Dose", "⚙️ Setup", "📋 Audit Log"])
        
        with tab1:
            master = get_prescriptions(target_patient)
            if master:
                opts = {f"{n} ({d})": (n, d) for n, d in master}
                sel = st.selectbox("Medication:", ["-- Select --"] + list(opts.keys()))
                if sel != "-- Select --":
                    n, d = opts[sel]
                    limit = get_safety_limit(target_patient, n) or 100.0
                    if get_24hr_total(target_patient, n) >= limit:
                        st.error("🛑 BLOCKED: 24h limit reached.")
                    elif st.button(f"Confirm Dose"):
                        add_med_log(target_patient, n, d, st.session_state.user)
                        st.success("Logged!"); st.rerun()
            else: st.info("No prescriptions set.")

        with tab2:
            if st.session_state.role == "Clinician":
                st.subheader("🛠️ Adjust Prescription & Safety Cap")
                drug_to_edit = st.selectbox("Medication to Configure:", ["Oxycodone", "Oxycontin", "CBD Oil"])
                new_dose = st.text_input("New Dose (e.g. 5ml)")
                new_cap = st.number_input("New 24h Safety Cap", value=GUIDELINE_MAX.get(drug_to_edit, 10.0))
                
                guideline = GUIDELINE_MAX.get(drug_to_edit, 999)
                override_needed = new_cap > guideline
                
                if override_needed:
                    st.warning(f"⚠️ This cap exceeds NICE guidelines ({guideline}).")
                    override = st.checkbox("I confirm this is clinically necessary.")
                else:
                    override = True
                
                if st.button("Confirm & Save Change"):
                    if not new_dose: st.error("Dose cannot be empty.")
                    elif not override: st.error("Please confirm the override.")
                    else:
                        add_prescription(target_patient, drug_to_edit, new_dose)
                        set_safety_limit(target_patient, drug_to_edit, new_cap)
                        log_audit(st.session_state.user, target_patient, "Prescription Change", f"{drug_to_edit} set to {new_dose}, Cap: {new_cap}")
                        st.success("Updated and Logged!"); st.rerun()
            else:
                st.info("🛡️ Clinicians only.")

        with tab3:
            st.subheader("📜 Audit History")
            logs = get_audit_logs(target_patient)
            if logs:
                st.table(pd.DataFrame(logs, columns=["Time", "Clinician", "Action", "Details"]))
            else: st.write("No changes yet.")

        # 3. History
        if h_all:
            st.divider()
            st.subheader("📊 Administration History")
            st.dataframe(pd.DataFrame(h_all, columns=["Med", "Dose", "Time", "By"]), use_container_width=True)