import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from database import init_db, add_user, get_meds, get_all_patients, get_last_dose_time, add_prescription, get_prescriptions

st.set_page_config(page_title="MedLog Pro", page_icon="🏥", layout="wide")
init_db()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'signup_iter' not in st.session_state:
    st.session_state.signup_iter = 0

# --- AUTH ---
if not st.session_state.logged_in:
    menu = st.sidebar.radio("Navigation", ["Login", "Sign Up"])
    if menu == "Sign Up":
        st.title("🏥 Register")
        u = st.text_input("Username", key=f"u_{st.session_state.signup_iter}")
        p = st.text_input("Password", type="password", key=f"p_{st.session_state.signup_iter}")
        r = st.selectbox("Role", ["Patient", "Clinician"], key=f"r_{st.session_state.signup_iter}")
        if st.button("Create Account"):
            if u and p:
                if add_user(u, p, r):
                    st.success("Account created!")
                    st.session_state.signup_iter += 1
                    st.rerun()
    else:
        st.title("🔐 Login")
        l_u = st.text_input("Username")
        l_p = st.text_input("Password", type="password")
        if st.button("Login"):
            conn = sqlite3.connect('meds.db')
            c = conn.cursor()
            c.execute('SELECT role FROM users WHERE username=? AND password=?', (l_u, l_p))
            res = c.fetchone()
            if res:
                st.session_state.logged_in, st.session_state.user, st.session_state.role = True, l_u, res[0]
                st.rerun()
            else: st.error("Invalid credentials.")

# --- DASHBOARD ---
else:
    st.sidebar.subheader(f"User: {st.session_state.user}")
    target_user = st.session_state.user

    if st.session_state.role == "Clinician":
        patients = get_all_patients()
        target_user = st.sidebar.selectbox("🔍 Select Patient:", ["Select Patient"] + patients)
        if target_user == "Select Patient":
            st.info("Select a patient from the sidebar.")
            st.stop()
        
        with st.expander(f"⚙️ Manage {target_user}'s Prescriptions", expanded=False):
            m_col1, m_col2 = st.columns(2)
            with m_col1: new_m = st.text_input("Drug Name")
            with m_col2: new_d = st.text_input("Dosage")
            if st.button("Add to List"):
                if new_m and new_d:
                    add_prescription(target_user, new_m, new_d)
                    st.rerun()
            st.divider()
            st.subheader("Quick-Add Defaults")
            q_cols = st.columns(3)
            if q_cols[0].button("➕ Oxycodone (5mg)"):
                add_prescription(target_user, "Oxycodone", "5mg"); st.rerun()
            if q_cols[1].button("➕ CBD oil (10mg)"):
                add_prescription(target_user, "CBD oil", "10mg"); st.rerun()
            if q_cols[2].button("➕ Oxycontin (10mg)"):
                add_prescription(target_user, "Oxycontin", "10mg"); st.rerun()

    st.title(f"Medication Log: {target_user}")

    # OVERALL STATUS
    last_overall = get_last_dose_time(target_user)
    if last_overall:
        diff = (datetime.now() - datetime.strptime(last_overall, "%Y-%m-%d %H:%M")).total_seconds() / 3600
        if diff > 4: st.error(f"🚨 ALERT: {diff:.1f} hrs since ANY medication.")
        else: st.success(f"✅ Last dose: {diff:.1f} hrs ago.")

    # REACTIVE DROPDOWN WITH DRUG-SPECIFIC TIMERS
    st.subheader("💊 Record a Dose")
    master_meds = get_prescriptions(target_user)
    
    if master_meds:
        # Create labels that include the "Last Taken" time
        options_map = {}
        for m_name, m_dose in master_meds:
            last_drug_time = get_last_dose_time(target_user, m_name)
            if last_drug_time:
                t_diff = (datetime.now() - datetime.strptime(last_drug_time, "%Y-%m-%d %H:%M")).total_seconds() / 3600
                label = f"{m_name} (Last: {t_diff:.1f}h ago)"
            else:
                label = f"{m_name} (Never logged)"
            options_map[label] = (m_name, m_dose)

        selected_label = st.selectbox("Search & Check Timing:", [""] + list(options_map.keys()))
        
        if selected_label != "":
            drug_info = options_map[selected_label]
            st.info(f"**Selected:** {drug_info[0]} | **Dosage:** {drug_info[1]}")
            
            if st.button(f"Confirm {drug_info[0]} Dose"):
                conn = sqlite3.connect('meds.db')
                c = conn.cursor()
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                c.execute('INSERT INTO medications VALUES (?,?,?,?)', (target_user, drug_info[0], drug_info[1], now))
                conn.commit()
                st.toast(f"Logged {drug_info[0]}!")
                st.rerun()
    else:
        st.warning("No meds assigned.")

    st.subheader("History")
    hist = get_meds(target_user)
    if hist:
        st.dataframe(pd.DataFrame(hist, columns=["Med", "Dose", "Time"]), use_container_width=True)

    if st.sidebar.button("Log Out"):
        st.session_state.logged_in = False
        st.rerun()