import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from database import init_db, add_user, get_meds, get_all_patients, get_last_dose_time

st.set_page_config(page_title="MedLog Shared Care", page_icon="🏥", layout="wide")
init_db()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'role' not in st.session_state:
    st.session_state.role = None
if 'signup_iter' not in st.session_state:
    st.session_state.signup_iter = 0

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
                    st.success(f"✅ Account for **{u}** ({role_map[r]}) created!")
                    if st.button("Clear form to add another user"):
                        st.session_state.signup_iter += 1
                        st.rerun()
                else:
                    st.error("❌ Username already exists.")
            else:
                st.warning("Please fill in all fields.")
    else:
        st.title("🔐 Login")
        u = st.text_input("Username", key="log_u")
        p = st.text_input("Password", type="password", key="log_p")
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
else:
    st.sidebar.title(f"User: {st.session_state.user}")
    st.sidebar.info(f"Role: {st.session_state.role}")
    target_user = st.session_state.user
    if st.session_state.role == "Clinician":
        patients = get_all_patients()
        if patients:
            target_user = st.sidebar.selectbox("Monitoring Patient:", patients)
            st.title(f"Clinical Dashboard: {target_user}")
        else:
            st.title("Clinician Dashboard")
            st.warning("No patients registered yet.")
    else:
        st.title(f"My Medication Log: {target_user}")

    last_time_str = get_last_dose_time(target_user)
    if last_time_str:
        last_dose_dt = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M")
        time_diff = datetime.now() - last_dose_dt
        hours_since = time_diff.total_seconds() / 3600
        if hours_since > 4:
            st.error(f"🚨 **ALERT:** No doses logged for {target_user} in the last {hours_since:.1f} hours!")
        else:
            st.success(f"✅ **On Track:** Last dose was {hours_since:.1f} hours ago.")
    else:
        st.info("No records found for this user.")

    with st.expander(f"➕ Add Entry for {target_user}"):
        with st.form("med_log_form", clear_on_submit=True):
            m_name = st.text_input("Medication Name")
            m_dose = st.text_input("Dosage")
            if st.form_submit_button("Submit Log"):
                if m_name and m_dose:
                    conn = sqlite3.connect('meds.db', check_same_thread=False)
                    c = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    c.execute('INSERT INTO medications VALUES (?,?,?,?)', (target_user, m_name, m_dose, now))
                    conn.commit()
                    conn.close()
                    st.rerun()

    st.subheader("Recent History")
    history = get_meds(target_user)
    if history:
        df = pd.DataFrame(history, columns=["Medication", "Dosage", "Time Logged"])
        st.dataframe(df, use_container_width=True)
    
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()