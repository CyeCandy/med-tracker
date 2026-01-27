import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from database import init_db, add_user, get_meds, get_all_patients, get_last_dose_time, add_prescription, get_prescriptions, get_24hr_total

st.set_page_config(page_title="MedLog Shared Care", layout="wide", initial_sidebar_state="expanded")
init_db()

def play_alarm():
    components.html('<audio autoplay><source src="https://cdn.pixabay.com/audio/2022/03/15/audio_731477782b.mp3" type="audio/mpeg"></audio>', height=0)

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
            r = st.selectbox("Role", ["Patient", "Clinician"])
            if st.button("Create Account"):
                if add_user(u, p, r): st.success("Created! Switch to Login.")
        else:
            if st.button("Sign In"):
                import sqlite3
                conn = sqlite3.connect('meds.db')
                c = conn.cursor()
                c.execute('SELECT role FROM users WHERE username=? AND password=?', (u, p))
                res = c.fetchone()
                if res:
                    st.session_state.logged_in, st.session_state.user, st.session_state.role = True, u, res[0]
                    st.rerun()
    else:
        st.write(f"**Current User:** {st.session_state.user}")
        st.write(f"**Role:** {st.session_state.role}")
        
        # CLINICIAN PATIENT SELECTOR
        target_patient = st.session_state.user
        if st.session_state.role == "Clinician":
            pts = get_all_patients()
            target_patient = st.selectbox("🔍 Managing Patient:", ["-- Select Patient --"] + pts)
        
        st.divider()
        if st.button("Log Out"):
            st.session_state.logged_in = False
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.logged_in:
    if st.session_state.role == "Clinician" and target_patient == "-- Select Patient --":
        st.title("Clinician Dashboard")
        st.info("Select a patient from the sidebar to view records or log doses on their behalf.")
    else:
        st.title(f"Care Record: {target_patient}")
        if st.session_state.role == "Clinician":
            st.warning(f"⚠️ You are currently viewing and logging for **{target_patient}**")

        # 1. Metrics & Safety
        col1, col2, col3 = st.columns(3)
        o_tot = get_24hr_total(target_patient, "Oxycodone")
        c_tot = get_24hr_total(target_patient, "CBD Oil")
        con_tot = get_24hr_total(target_patient, "Oxycontin")
        col1.metric("Oxycodone (24h)", f"{o_tot} ml", "/ 35ml")
        col2.metric("CBD Oil (24h)", f"{c_tot} ml", "/ 4ml")
        col3.metric("Oxycontin (24h)", f"{con_tot} ml")

        # 2. Alerts
        alarm = False
        for drug, limit in [("Oxycontin", 12), ("Oxycodone", 4)]:
            last = get_last_dose_time(target_patient, drug)
            if last:
                diff = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() / 3600
                if diff >= limit:
                    st.error(f"🔔 {drug} is DUE for {target_patient} ({diff:.1f}h ago)"); alarm = True
        if alarm: play_alarm()

        # 3. RECORDING (PROXY CAPABILITY)
        st.subheader(f"💊 Log Dose for {target_patient}")
        master = get_prescriptions(target_patient)
        if master:
            opts = {f"{n} ({d})": (n, d) for n, d in master}
            sel = st.selectbox("Select Medication:", [""] + list(opts.keys()))
            if sel:
                n, d = opts[sel]
                if n == "Oxycodone" and o_tot >= 35:
                    st.error("🛑 Blocked: 24h limit reached.")
                else:
                    if st.button(f"Confirm Dose as {st.session_state.user}"):
                        import sqlite3
                        conn = sqlite3.connect('meds.db'); c = conn.cursor()
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        c.execute('INSERT INTO medications VALUES (?,?,?,?)', (target_patient, n, d, now))
                        conn.commit(); st.success(f"Logged {n} for {target_patient}"); st.rerun()
        else:
            st.info("No medications prescribed. Clinicians can add them in the sidebar setup (optional: add setup here).")

        # 4. SHARED HISTORY
        st.subheader(f"📜 {target_patient}'s History")
        h = get_meds(target_patient)
        if h: 
            st.dataframe(pd.DataFrame(h, columns=["Medication", "Dosage", "Time Taken"]), use_container_width=True)
        else:
            st.write("No doses logged yet.")
else:
    st.title("🏥 Home Care MedLog")
    st.write("Please use the side panel to sign in.")