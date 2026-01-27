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
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            conn = sqlite3.connect('meds.db')
            c = conn.cursor()
            c.execute('SELECT role FROM users WHERE username=? AND password=?', (u, p))
            res = c.fetchone()
            if res:
                st.session_state.logged_in, st.session_state.user, st.session_state.role = True, u, res[0]
                st.rerun()
    with t2:
        nu = st.text_input("New Username")
        np = st.text_input("New Password", type="password")
        nr = st.selectbox("Role", ["Patient", "Clinician"])
        if st.button("Register"):
            if add_user(nu, np, nr): st.success("Account created!"); st.rerun()

# --- MAIN PAGE STRUCTURE ---
else:
    # Always show sidebar
    st.sidebar.title("🏥 Navigation")
    st.sidebar.write(f"Logged in as: **{st.session_state.user}**")
    
    selected_patient = None

    if st.session_state.role == "Clinician":
        all_pts = get_all_patients()
        selected_patient = st.sidebar.selectbox("🔍 Patient Selector", ["-- Choose Patient --"] + all_pts)
        if selected_patient == "-- Choose Patient --":
            selected_patient = None
    else:
        selected_patient = st.session_state.user

    # Main Panel Content
    if not selected_patient:
        st.title("Welcome to MedLog")
        st.info("👈 Please select a patient from the sidebar to view their clinical dashboard.")
    else:
        st.title(f"Care Dashboard: {selected_patient}")
        
        # 1. Clinician Setup
        if st.session_state.role == "Clinician":
            with st.expander("⚙️ Prescription Management", expanded=False):
                c1, c2, c3 = st.columns(3)
                if c1.button("➕ Oxycontin 100ml"): add_prescription(selected_patient, "Oxycontin", "100 ml"); st.rerun()
                if c2.button("➕ Oxycodone 7ml"): add_prescription(selected_patient, "Oxycodone", "7 ml"); st.rerun()
                if c3.button("➕ CBD Oil 1ml"): add_prescription(selected_patient, "CBD Oil", "1 ml"); st.rerun()

        # 2. Safety Metrics
        st.subheader("📊 24-Hour Totals")
        m1, m2, m3 = st.columns(3)
        o_tot = get_24hr_total(selected_patient, "Oxycodone")
        c_tot = get_24hr_total(selected_patient, "CBD Oil")
        con_tot = get_24hr_total(selected_patient, "Oxycontin")
        m1.metric("Oxycodone", f"{o_tot} ml", "/ 35 ml")
        m2.metric("CBD Oil", f"{c_tot} ml", "/ 4 ml")
        m3.metric("Oxycontin", f"{con_tot} ml")

        # 3. Alarms
        alarm = False
        for drug, limit in [("Oxycontin", 12), ("Oxycodone", 4)]:
            last = get_last_dose_time(selected_patient, drug)
            if last:
                diff = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() / 3600
                if diff >= limit:
                    st.error(f"🔔 {drug} is DUE ({diff:.1f}h ago)"); alarm = True
        if alarm: play_alarm()

        # 4. Log Meds
        st.divider()
        st.subheader("💊 Log Dose")
        master = get_prescriptions(selected_patient)
        if master:
            opts = {f"{n} ({d})": (n, d) for n, d in master}
            sel = st.selectbox("Select Med:", [""] + list(opts.keys()))
            if sel:
                n, d = opts[sel]
                if n == "Oxycodone" and o_tot >= 35:
                    st.error("🛑 Daily limit reached.")
                elif st.button(f"Log {n}"):
                    conn = sqlite3.connect('meds.db')
                    c = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    c.execute('INSERT INTO medications VALUES (?,?,?,?)', (selected_patient, n, d, now))
                    conn.commit()
                    st.rerun()

        # 5. History
        st.subheader("📜 History")
        h = get_meds(selected_patient)
        if h: st.dataframe(pd.DataFrame(h, columns=["Med", "Dose", "Time"]), use_container_width=True)

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()