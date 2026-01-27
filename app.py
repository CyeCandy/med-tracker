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

# --- AUTH ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab2:
        u = st.text_input("New Username")
        p = st.text_input("New Password", type="password")
        r = st.selectbox("Role", ["Patient", "Clinician"])
        if st.button("Register"):
            if add_user(u, p, r): st.success("Account created!"); st.rerun()
    with tab1:
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

# --- DASHBOARD ---
else:
    st.sidebar.subheader(f"Logged in: {st.session_state.user}")
    target_user = st.session_state.user

    if st.session_state.role == "Clinician":
        patients = get_all_patients()
        target_user = st.sidebar.selectbox("🔍 Select Patient:", ["Select Patient"] + patients)
        if target_user == "Select Patient": 
            st.title("Welcome, Clinician")
            st.info("Please select a patient from the sidebar to manage their care.")
            st.stop()
        
        # THIS SECTION POPULATES THE LOGGING LIST
        with st.expander("⚙️ Clinical Setup: Define Prescriptions", expanded=True):
            st.write("Medications added here will appear in the 'Log Medication' dropdown below.")
            c1, c2, c3 = st.columns(3)
            if c1.button("➕ Oxycontin (100ml)"):
                add_prescription(target_user, "Oxycontin", "100 ml"); st.rerun()
            if c2.button("➕ Oxycodone (7ml)"):
                add_prescription(target_user, "Oxycodone", "7 ml"); st.rerun()
            if c3.button("➕ CBD Oil (1ml)"):
                add_prescription(target_user, "CBD Oil", "1 ml"); st.rerun()
            
            st.write("---")
            st.write("Custom Medication:")
            custom_n = st.text_input("Drug Name")
            custom_d = st.text_input("Dose (e.g. 5 ml)")
            if st.button("Add Custom Med"):
                if custom_n and custom_d:
                    add_prescription(target_user, custom_n, custom_d); st.rerun()

    st.title(f"Care Dashboard: {target_user}")

    # CUMULATIVE SUMMARY
    st.subheader("📊 24-Hour Totals")
    col1, col2, col3 = st.columns(3)
    o_tot = get_24hr_total(target_user, "Oxycodone")
    c_tot = get_24hr_total(target_user, "CBD Oil")
    con_tot = get_24hr_total(target_user, "Oxycontin")
    
    col1.metric("Oxycodone", f"{o_tot} ml", "Limit: 35ml")
    col2.metric("CBD Oil", f"{c_tot} ml", "Limit: 4ml")
    col3.metric("Oxycontin", f"{con_tot} ml")

    # LOGGING SECTION
    st.divider()
    st.subheader("💊 Log Medication")
    master_list = get_prescriptions(target_user)
    
    if not master_list:
        st.warning("⚠️ No medications have been prescribed yet. A Clinician must add them in the 'Clinical Setup' section above before you can log a dose.")
    else:
        options_map = {}
        for name, dose in master_list:
            last_t = get_last_dose_time(target_user, name)
            diff = f"{(datetime.now() - datetime.strptime(last_t, '%Y-%m-%d %H:%M')).total_seconds()/3600:.1f}h ago" if last_t else "Never"
            label = f"{name} ({dose}) - Last: {diff}"
            options_map[label] = (name, dose)

        selected_label = st.selectbox("Select Medication to Record:", [""] + list(options_map.keys()))
        
        if selected_label:
            n, d = options_map[selected_label]
            if n == "Oxycodone" and o_tot >= 35:
                st.error("🛑 Blocked: 24-hour limit of 35ml reached.")
            else:
                if st.button(f"Log {n} {d} Now"):
                    conn = sqlite3.connect('meds.db')
                    c = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    c.execute('INSERT INTO medications VALUES (?,?,?,?)', (target_user, n, d, now))
                    conn.commit()
                    st.rerun()

    st.subheader("History")
    hist = get_meds(target_user)
    if hist: st.dataframe(pd.DataFrame(hist, columns=["Med", "Dose", "Time"]), use_container_width=True)
    if st.sidebar.button("Logout"): st.session_state.logged_in = False; st.rerun()
    