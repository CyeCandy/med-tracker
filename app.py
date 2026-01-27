import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from database import init_db, add_user, get_meds, get_all_patients, get_last_dose_time

st.set_page_config(page_title="MedLog Shared Care", page_icon="🏥", layout="wide")
init_db()

# Session State
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'role' not in st.session_state:
    st.session_state.role = None
if 'signup_iter' not in st.session_state:
    st.session_state.signup_iter = 0

# --- AUTH / SIGNUP ---
if not st.session_state.logged_in:
    menu = st.sidebar.radio("Navigation", ["Login", "Sign Up"])
    
    if menu == "Sign Up":
        st.title("🏥 Register New User")
        u = st.text_input("Choose Username", key=f"reg_u_{st.session_state.signup_iter}")
        p = st.text_input("Choose Password", type="password", key=f"reg_p_{st.session_state.signup_iter}")
        r = st.selectbox("Assign Role", ["Patient", "Clinician/Family"], key=f"reg_r_{st.session_state.signup_iter}")
        role_map = {"Patient": "Patient", "Clinician/Family": "Clinician"}
        
        if st.button("Register User"):
            if u and p:
                if add_user(u, p, role_map[r]):
                    st.success(f"✅ Account for **{u}** created!")
                    if st.button("Clear & Add Another"):
                        st.session_state.signup_iter += 1
                        st.rerun()
                else:
                    st.error("❌ Username already exists.")

    else:
        st.title("🔐 Login")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            conn = sqlite3.connect('meds.db', check_same_thread=False)
            c = conn.cursor()
            c.execute('SELECT role FROM users WHERE username=? AND password=?', (u, p))
            res = c.fetchone()
            conn.close()
            if res:
                st.session_state.logged_in = True
                st.session_state.user = u
                st.session_state.role = res[0]
                st.rerun()
            else:
                st.error("Invalid credentials.")

# --- DASHBOARD ---
else:
    st.sidebar.title(f"Welcome, {st.session_state.user}")
    
    # Identify who we are looking at
    target_user = st.session_state.user 
    
    if st.session_state.role == "Clinician":
        st.title("👨‍⚕️ Clinician Control Panel")
        patients = get_all_patients()
        
        if patients:
            # SEARCHABLE DROPDOWN
            target_user = st.sidebar.selectbox("🔍 Search/Select Patient:", patients)
            st.subheader(f"Monitoring: {target_user}")
        else:
            st.warning("No patients found in system.")
    else:
        st.title(f"📊 My Health Log: {st.session_state.user}")

    # --- STATUS ALERT ---
    last_time_str = get_last_dose_time(target_user)
    if last_time_str:
        last_dose_dt = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M")
        hours_since = (datetime.now() - last_dose_dt).total_seconds() / 3600
        if hours_since > 4:
            st.error(f"🚨 ALERT: {target_user} is {hours_since:.1f} hours overdue!")
        else:
            st.success(f"✅ {target_user} is on track. Last dose: {hours_since:.1f} hours ago.")

    # --- CLINICIAN ENTRY FORM ---
    with st.expander(f"💊 Log Medication for {target_user}", expanded=True):
        with st.form("entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                drug = st.text_input("Medication Name")
            with col2:
                dose = st.text_input("Dosage (e.g., 500mg)")
            
            submit = st.form_submit_button("Record Dose")
            if submit:
                if drug and dose:
                    conn = sqlite3.connect('meds.db', check_same_thread=False)
                    c = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    c.execute('INSERT INTO medications VALUES (?,?,?,?)', (target_user, drug, dose, now))
                    conn.commit()
                    conn.close()
                    st.toast(f"Recorded {drug} for {target_user}")
                    st.rerun()

    # --- HISTORY ---
    st.subheader(f"📜 {target_user}'s Dose History")
    history = get_meds(target_user)
    if history:
        df = pd.DataFrame(history, columns=["Medication", "Dosage", "Logged At"])
        st.dataframe(df, use_container_width=True)
    
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()