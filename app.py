import streamlit as st
import sqlite3
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from database import init_db, add_user, get_meds, get_all_patients, get_last_dose_time, add_prescription, get_prescriptions, get_24hr_total

st.set_page_config(page_title="MedLog Safety Pro", page_icon="🏥", layout="wide")
init_db()

def play_alarm():
    sound_html = """<audio autoplay><source src="https://cdn.pixabay.com/audio/2022/03/15/audio_731477782b.mp3" type="audio/mpeg"></audio>"""
    components.html(sound_html, height=0)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- AUTH ---
if not st.session_state.logged_in:
    menu = st.sidebar.radio("Navigation", ["Login", "Sign Up"])
    if menu == "Sign Up":
        st.title("🏥 Register")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        r = st.selectbox("Role", ["Patient", "Clinician"])
        if st.button("Create"):
            if add_user(u, p, r): st.success("Created!"); st.rerun()
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

# --- DASHBOARD ---
else:
    st.sidebar.subheader(f"User: {st.session_state.user}")
    target_user = st.session_state.user

    if st.session_state.role == "Clinician":
        patients = get_all_patients()
        target_user = st.sidebar.selectbox("🔍 Patient:", ["Select Patient"] + patients)
        if target_user == "Select Patient": st.stop()
        
        with st.expander("⚙️ Set Prescriptions & Quick-Add", expanded=False):
            q1, q2, q3 = st.columns(3)
            if q1.button("➕ Oxycontin 100ml"):
                add_prescription(target_user, "Oxycontin", "100 ml"); st.rerun()
            if q2.button("➕ Oxycodone 7ml"):
                add_prescription(target_user, "Oxycodone", "7 ml"); st.rerun()
            if q3.button("➕ CBD Oil 1ml"):
                add_prescription(target_user, "CBD Oil", "1 ml"); st.rerun()

    st.title(f"Care Dashboard: {target_user}")

    # --- 24-HOUR CUMULATIVE SAFETY MONITOR ---
    st.subheader("📊 24-Hour Dosage Summary")
    s_col1, s_col2, s_col3 = st.columns(3)
    
    oxy_total = get_24hr_total(target_user, "Oxycodone")
    cbd_total = get_24hr_total(target_user, "CBD Oil")
    contin_total = get_24hr_total(target_user, "Oxycontin")

    s_col1.metric("Oxycodone Total", f"{oxy_total} ml", "/ 35 ml")
    s_col2.metric("CBD Oil Total", f"{cbd_total} ml", "/ 4 ml")
    s_col3.metric("Oxycontin Total", f"{contin_total} ml")

    # Alarm/Warning Logic
    alarm_triggered = False
    
    # Oxycontin 12h check
    last_contin = get_last_dose_time(target_user, "Oxycontin")
    if last_contin:
        if (datetime.now() - datetime.strptime(last_contin, "%Y-%m-%d %H:%M")).total_seconds() / 3600 >= 12:
            st.error("🔔 DUE: Oxycontin (12h elapsed)"); alarm_triggered = True

    # Oxycodone 4h check
    last_codone = get_last_dose_time(target_user, "Oxycodone")
    if last_codone:
        if (datetime.now() - datetime.strptime(last_codone, "%Y-%m-%d %H:%M")).total_seconds() / 3600 >= 4:
            st.error("🔔 DUE: Oxycodone (4h elapsed)"); alarm_triggered = True

    # Limit Warnings
    if oxy_total >= 35:
        st.error("🛑 OXYCODONE LIMIT REACHED (35ml). Administration blocked.")
    if cbd_total > 4:
        st.warning(f"⚠️ CBD OIL WARNING: {cbd_total}ml exceeds daily 4ml guideline.")

    if alarm_triggered: play_alarm()

    # --- RECORDING ---
    st.divider()
    st.subheader("💊 Log Medication")
    master_meds = get_prescriptions(target_user)
    if master_meds:
        options_map = {}
        for name, dose in master_meds:
            last_t = get_last_dose_time(target_user, name)
            diff_str = f"{(datetime.now() - datetime.strptime(last_t, '%Y-%m-%d %H:%M')).total_seconds()/3600:.1f}h ago" if last_t else "Never"
            label = f"{name} ({dose}) - Last: {diff_str}"
            options_map[label] = (name, dose)

        sel = st.selectbox("Select from Prescribed List:", [""] + list(options_map.keys()))
        if sel:
            n, d = options_map[sel]
            # BLOCK OXYCODONE IF AT LIMIT
            if n == "Oxycodone" and oxy_total >= 35:
                st.error("Submission blocked: Daily limit reached.")
            else:
                if st.button(f"Confirm {n} {d}"):
                    conn = sqlite3.connect('meds.db')
                    c = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    c.execute('INSERT INTO medications VALUES (?,?,?,?)', (target_user, n, d, now))
                    conn.commit()
                    st.rerun()

    st.subheader("Full Log History")
    hist = get_meds(target_user)
    if hist: st.dataframe(pd.DataFrame(hist, columns=["Med", "Dose", "Time"]), use_container_width=True)
    if st.sidebar.button("Logout"): st.session_state.logged_in = False; st.rerun()