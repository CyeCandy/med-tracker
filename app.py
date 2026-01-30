import streamlit as st
import pandas as pd
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from database import *

# --- CONFIG ---
CLINIC_KEY = "CARE2026"
SENDER_EMAIL = "" 
SENDER_PASS = "xxxx yyyy zzzz wwww" 

GUIDELINE_MAX = {"Oxycodone": 40.0, "Oxycontin": 80.0, "CBD Oil": 5.0}

st.set_page_config(page_title="MedLog Shared Care", layout="wide")
init_db()

def send_free_sms(to_gateway_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_gateway_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASS)
            smtp.send_message(msg)
        return True
    except:
        return False

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
            st.write("--- SMS Setup ---")
            phone = st.text_input("Phone Number")
            carrier = st.selectbox("Carrier", ["None", "EE (UK)", "O2 (UK)", "Verizon (US)", "AT&T (US)", "T-Mobile (US)"])
            gateways = {"EE (UK)": "@mms.ee.co.uk", "O2 (UK)": "@mms.o2.co.uk", "Verizon (US)": "@vtext.com", "AT&T (US)": "@txt.att.net", "T-Mobile (US)": "@tmomail.net"}
            full_gateway = f"{phone}{gateways.get(carrier, '')}" if carrier != "None" else ""

            if st.button("Create Account"):
                if r != "Patient" and code != CLINIC_KEY: st.error("Invalid Clinic Key.")
                elif add_user(u, p, r, full_gateway): st.success("Account created!")
                else: st.error("Username taken.")
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
        st.info("Select a patient from the sidebar.")
    else:
        st.title(f"Care Record: {target_patient}")
        h_all = get_meds(target_patient)

        # 1. Alarms
        for drug in ["Oxycodone", "Oxycontin", "CBD Oil"]:
            curr = get_24hr_total(target_patient, drug)
            limit = get_safety_limit(target_patient, drug) or 100.0
            if curr >= limit:
                st.error(f"🚨 {drug} 24h limit reached! ({curr}/{limit})")

        tab1, tab2, tab3 = st.tabs(["💊 Log Dose", "⚙️ Setup", "📋 Audit Log"])
        
        with tab1:
            st.subheader("Administer Medication")
            master = get_prescriptions(target_patient)
            if master:
                # We build a dictionary mapping the "Display Name" to the (Drug Name, Dosage)
                opts = {f"{n} ({d})": (n, d) for n, d in master}
                sel = st.selectbox("Select from Prescription:", ["-- Select --"] + list(opts.keys()))
                
                if sel != "-- Select --":
                    drug_name, dosage_str = opts[sel]
                    
                    # Safety Check before logging
                    curr_24 = get_24hr_total(target_patient, drug_name)
                    limit = get_safety_limit(target_patient, drug_name) or 100.0
                    
                    if curr_24 >= limit:
                        st.warning(f"🛑 Cannot Log: {drug_name} 24h limit already reached.")
                    elif st.button(f"Confirm Dose: {drug_name} {dosage_str}"):
                        add_med_log(target_patient, drug_name, dosage_str, st.session_state.user)
                        st.success(f"Logged {drug_name} for {target_patient}!"); st.rerun()
            else:
                st.info("No prescriptions found for this patient.")

        with tab2:
            if st.session_state.role == "Clinician":
                st.subheader("🛠️ Prescription Management")
                drug_to_edit = st.selectbox("Medication:", ["Oxycodone", "Oxycontin", "CBD Oil"])
                new_dose = st.text_input("Standard Dosage (e.g., 5ml or 10mg)")
                new_cap = st.number_input("Max 24h Total (Numeric Only)", value=GUIDELINE_MAX.get(drug_to_edit, 10.0))
                
                guideline = GUIDELINE_MAX.get(drug_to_edit, 999)
                override = True
                if new_cap > guideline:
                    st.warning(f"⚠️ Exceeds NICE guidelines ({guideline})")
                    override = st.checkbox("Confirm Clinical Override")
                
                if st.button("Save Prescription"):
                    if not new_dose:
                        st.error("Please enter a dosage string.")
                    elif not override:
                        st.error("Please confirm the safety override.")
                    else:
                        add_prescription(target_patient, drug_to_edit, new_dose)
                        set_safety_limit(target_patient, drug_to_edit, new_cap)
                        log_audit(st.session_state.user, target_patient, "Dose Change", f"{drug_to_edit} -> {new_dose}, Cap: {new_cap}")
                        
                        sms = get_user_sms(target_patient)
                        if sms:
                            send_free_sms(sms, "Med Alert", f"Your {drug_to_edit} dose updated to {new_dose}")
                        st.success("Updated!"); st.rerun()
            else: st.info("Only Clinicians can modify prescriptions.")

        with tab3:
            st.subheader("📜 Audit History")
            logs = get_audit_logs(target_patient)
            if logs: st.table(pd.DataFrame(logs, columns=["Time", "Clinician", "Action", "Details"]))

        if h_all:
            st.divider()
            st.dataframe(pd.DataFrame(h_all, columns=["Med", "Dose", "Time", "By"]), use_container_width=True)