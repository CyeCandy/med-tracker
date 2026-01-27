import streamlit as st
import sqlite3
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from database import init_db, add_user, get_meds, get_all_patients, get_last_dose_time, add_prescription, get_prescriptions, get_24hr_total

st.set_page_config(page_title="MedLog Pro", page_icon="🏥", layout="wide")
init_db()

def play_alarm():
    sound_html = """<audio autoplay><source src="https://cdn.pixabay.com/audio/2022/03/15/audio_731477782b.mp3" type="audio/mpeg"></audio>"""
    components.html(sound_html, height=0)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- AUTHENTICATION ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab2:
        st.subheader("Create New Account")
        u = st.text_input("New Username")
        p = st.text_input("New Password", type="password")
        r = st.selectbox("Role", ["Patient", "Clinician"])
        if st.button("Register Account"):
            if add_user(u, p, r): 
                st.success("Account created! Please log in.")
    with tab1:
        st.subheader("Login")
        l_u = st.text_input("Username")
        l_p = st.text_input("Password", type="password")
        if st.button("Log In"):
            conn = sqlite3.connect('meds.db')
            c = conn.cursor()
            c.execute('SELECT role FROM users WHERE username=? AND password=?', (l_u, l_p))
            res = c.fetchone()
            if res:
                st.session_state.logged_in, st.session_state.user, st.session_state.role = True, l_u, res[0]
                st.rerun()
            else:
                st.error("Invalid credentials.")

# --- MAIN DASHBOARD AREA ---
else:
    st.sidebar.title(f"🏥 MedLog")
    st.sidebar.write(f"**User:** {st.session_state.user}")
    st.sidebar.write(f"**Role:** {st.session_state.role}")
    
    target_user = st.session_state.user

    # CLINICIAN SELECTOR
    if st.session_state.role == "Clinician":
        patients = get_all_patients()
        target_user = st.sidebar.selectbox("🔍 Select Patient to Manage:", ["Select Patient"] + patients)
        
        if target_user == "Select Patient":
            st.title("Clinician Overview")
            st.info("Please select a patient from the sidebar to view the dashboard.")
            if st.sidebar.button("Log Out"):
                st.session_state.logged_in = False
                st.rerun()
            st.stop() # Stops execution here until a patient is picked

    # --- THE DASHBOARD CONTENT (Only shows if a patient is active) ---
    st.title(f"Care Dashboard: {target_user}")

    # 1. TOP SECTION: CLINICIAN SETUP (Hidden from Patients)
    if st.session_state.role == "Clinician":
        with st.expander("⚙️ Clinical Setup: Define Prescriptions", expanded=True):
            st.write("Medications added here populate the list below.")
            c1, c2, c3 = st.columns(3)
            if c1.button("➕ Oxycontin (100ml)"):
                add_prescription(target_user, "Oxycontin", "100 ml"); st.rerun()
            if c2.button("➕ Oxycodone (7ml)"):
                add_prescription(target_user, "Oxycodone", "7 ml"); st.rerun()
            if c3.button("➕ CBD Oil (1ml)"):
                add_prescription(target_user, "CBD Oil", "1 ml"); st.rerun()
            
            st.divider()
            custom_n = st.text_input("Add Custom Drug Name")
            custom_d = st.text_input("Dose (e.g. 5 ml)")
            if st.button("Add Custom Prescription"):
                if custom_n and custom_d:
                    add_prescription(target_user, custom_n, custom_d); st.rerun()

    # 2. SAFETY SUMMARY
    st.subheader("📊 24-Hour Cumulative Totals")
    col1, col2, col3 = st.columns(3)
    o_tot = get_24hr_total(target_user, "Oxycodone")
    c_tot = get_24hr_total(target_user, "CBD Oil")
    con_tot = get_24hr_total(target_user, "Oxycontin")
    
    col1.metric("Oxycodone", f"{o_tot} ml", "Max 35ml")
    col2.metric("CBD Oil", f"{c_tot} ml", "Limit 4ml")
    col3.metric("Oxycontin", f"{con_tot} ml")

    # 3. ALARM CHECKS
    alarm = False
    l_contin = get_last_dose_time(target_user, "Oxycontin")
    if l_contin:
        if (datetime.now() - datetime.strptime(l_contin, "%Y-%m-%d %H:%M")).total_seconds() / 3600 >= 12:
            st.error("🔔 Oxycontin is DUE (12h elapsed)"); alarm = True
            
    l_codone = get_last_dose_time(target_user, "Oxycodone")
    if l_codone:
        if (datetime.now() - datetime.strptime(l_codone, "%Y-%m-%d %H:%M")).total_seconds() / 3600 >= 4:
            st.error("🔔 Oxycodone is DUE (4h elapsed)"); alarm = True
    
    if alarm: play_alarm()

    # 4. LOGGING DOSE
    st.divider()
    st.subheader("💊 Record Medication Dose")
    master_list = get_prescriptions(target_user)
    
    if not master_list:
        st.warning("⚠️ No medications prescribed. A clinician must use the setup section above.")
    else:
        options_map = {}
        for name, dose in master_list:
            last_t = get_last_dose_time(target_user, name)
            diff = f"{(datetime.now() - datetime.strptime(last_t, '%Y-%m-%d %H:%M')).total_seconds()/3600:.1f}h ago" if last_t else "Never"
            label = f"{name} ({dose}) - Last: {diff}"
            options_map[label] = (name, dose)

        sel_label = st.selectbox("Choose medication:", [""] + list(options_map.keys()))
        if sel_label:
            n, d = options_map[sel_label]
            if n == "Oxycodone" and o_tot >= 35:
                st.error("🛑 STOP: 35ml limit reached. Logging blocked.")
            else:
                if st.button(f"Confirm Dose: {n} {d}"):
                    conn = sqlite3.connect('meds.db')
                    c = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    c.execute('INSERT INTO medications VALUES (?,?,?,?)', (target_user, n, d, now))
                    conn.commit()
                    st.success("Dose logged successfully!")
                    st.rerun()

    # 5. HISTORY
    st.subheader("📜 Medication History")
    hist = get_meds(target_user)
    if hist:
        df = pd.DataFrame(hist, columns=["Medication", "Dosage", "Logged At"])
        st.dataframe(df, use_container_width=True)

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()