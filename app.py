import streamlit as st
import sqlite3
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from database import init_db, add_user, get_meds, get_all_patients, get_last_dose_time, add_prescription, get_prescriptions, get_24hr_total

st.set_page_config(page_title="MedLog Shared Care", page_icon="🏥", layout="wide")
init_db()

# Function to play alarm sound
def play_alarm():
    # This uses a standard notification sound URL
    sound_html = """
    <audio autoplay>
      <source src="https://cdn.pixabay.com/audio/2022/03/15/audio_731477782b.mp3" type="audio/mpeg">
    </audio>
    """
    components.html(sound_html, height=0)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- AUTHENTICATION ---
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
        
        with st.expander("⚙️ Set Prescriptions", expanded=False):
            st.subheader("Quick-Add Specified Schedules")
            q1, q2 = st.columns(2)
            if q1.button("➕ Oxycontin 100ml (12h)"):
                add_prescription(target_user, "Oxycontin", "100 ml"); st.rerun()
            if q2.button("➕ Oxycodone 7ml (4h)"):
                add_prescription(target_user, "Oxycodone", "7 ml"); st.rerun()

    st.title(f"Medication Log: {target_user}")

    # --- ALARM & SAFETY LOGIC ---
    alarm_triggered = False
    
    # Check Oxycontin (12h)
    last_contin = get_last_dose_time(target_user, "Oxycontin")
    if last_contin:
        c_diff = (datetime.now() - datetime.strptime(last_contin, "%Y-%m-%d %H:%M")).total_seconds() / 3600
        if c_diff >= 12:
            st.error(f"🔔 DUE NOW: Oxycontin (Last dose {c_diff:.1f}h ago)")
            alarm_triggered = True
            
    # Check Oxycodone (4h)
    last_codone = get_last_dose_time(target_user, "Oxycodone")
    if last_codone:
        o_diff = (datetime.now() - datetime.strptime(last_codone, "%Y-%m-%d %H:%M")).total_seconds() / 3600
        if o_diff >= 4:
            st.error(f"🔔 DUE NOW: Oxycodone (Last dose {o_diff:.1f}h ago)")
            alarm_triggered = True

    # 24hr Safety Limit for Oxycodone
    oxy_total = get_24hr_total(target_user, "Oxycodone")
    if oxy_total >= 35:
        st.warning(f"🛑 24HR LIMIT REACHED: {oxy_total}ml Oxycodone taken. STOP.")
    
    # Play sound if anything is due
    if alarm_triggered:
        play_alarm()

    # --- LOGGING ---
    st.subheader("💊 Record Dose")
    master_meds = get_prescriptions(target_user)
    if master_meds:
        options_map = {}
        for m_name, m_dose in master_meds:
            last_t = get_last_dose_time(target_user, m_name)
            if last_t:
                diff = (datetime.now() - datetime.strptime(last_t, "%Y-%m-%d %H:%M")).total_seconds() / 3600
                label = f"{m_name} ({m_dose}) - {diff:.1f}h ago"
            else: label = f"{m_name} ({m_dose}) - Never logged"
            options_map[label] = (m_name, m_dose)

        sel = st.selectbox("Select Med:", [""] + list(options_map.keys()))
        if sel:
            name, dose = options_map[sel]
            if st.button(f"Confirm {name} {dose}"):
                conn = sqlite3.connect('meds.db')
                c = conn.cursor()
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                c.execute('INSERT INTO medications VALUES (?,?,?,?)', (target_user, name, dose, now))
                conn.commit()
                st.rerun()

    st.subheader("History")
    hist = get_meds(target_user)
    if hist: st.dataframe(pd.DataFrame(hist, columns=["Med", "Dose", "Time"]), use_container_width=True)
    if st.sidebar.button("Logout"): st.session_state.logged_in = False; st.rerun()
    