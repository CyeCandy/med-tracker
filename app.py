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
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    with tab2:
        st.subheader("Create New Account")
        u = st.text_input("New Username")
        p = st.text_input("New Password", type="password")
        r = st.selectbox("I am a...", ["Patient", "Clinician"])
        if st.button("Create Account"):
            if u and p:
                if add_user(u, p, r): st.success("Success! Now go to the Login tab.")
            else: st.warning("Fields cannot be empty.")
    with tab1:
        st.subheader("Login")
        l_u = st.text_input("Username")
        l_p = st.text_input("Password", type="password")
        if st.button("Sign In"):
            conn = sqlite3.connect('meds.db')
            c = conn.cursor()
            c.execute('SELECT role FROM users WHERE username=? AND password=?', (l_u, l_p))
            res = c.fetchone()
            if res:
                st.session_state.logged_in, st.session_state.user, st.session_state.role = True, l_u, res[0]
                st.rerun()
            else: st.error("Invalid credentials.")

# --- MAIN DASHBOARD ---
else:
    st.sidebar.title(f"🏥 MedLog Pro")
    st.sidebar.markdown(f"**Logged in:** `{st.session_state.user}`")
    st.sidebar.info(f"Role: {st.session_state.role}")
    
    target_user = st.session_state.user

    # CLINICIAN LOGIC
    if st.session_state.role == "Clinician":
        patients = get_all_patients()
        target_user = st.sidebar.selectbox("🔍 Select Patient to View:", ["-- Select --"] + patients)
        
        if target_user == "-- Select --":
            st.title("Welcome, Clinician")
            st.markdown("### To get started:")
            st.write("1. Create a **Patient** account if you haven't yet.")
            st.write("2. Select that patient from the **sidebar dropdown**.")
            st.write("3. Once selected, their full dashboard will appear here.")
            if st.sidebar.button("Logout"):
                st.session_state.logged_in = False
                st.rerun()
            st.stop() # Main page content below won't run until patient is selected

    # --- DASHBOARD VISUALS ---
    st.title(f"Dashboard: {target_user}")

    # 1. Clinician Tools
    if st.session_state.role == "Clinician":
        with st.expander("⚙️ Clinical Setup & Prescriptions", expanded=True):
            st.write("Quick-add common schedules for this patient:")
            c1, c2, c3 = st.columns(3)
            if c1.button("➕ Oxycontin (100ml)"): add_prescription(target_user, "Oxycontin", "100 ml"); st.rerun()
            if c2.button("➕ Oxycodone (7ml)"): add_prescription(target_user, "Oxycodone", "7 ml"); st.rerun()
            if c3.button("➕ CBD Oil (1ml)"): add_prescription(target_user, "CBD Oil", "1 ml"); st.rerun()

    # 2. Cumulative Dashboard
    st.subheader("📊 24-Hour Safety Metrics")
    m1, m2, m3 = st.columns(3)
    o_tot = get_24hr_total(target_user, "Oxycodone")
    c_tot = get_24hr_total(target_user, "CBD Oil")
    con_tot = get_24hr_total(target_user, "Oxycontin")
    
    m1.metric("Oxycodone", f"{o_tot} ml", "Target: <35ml")
    m2.metric("CBD Oil", f"{c_tot} ml", "Target: <4ml")
    m3.metric("Oxycontin", f"{con_tot} ml")

    # 3. Alarms
    alarm = False
    for drug, limit in [("Oxycontin", 12), ("Oxycodone", 4)]:
        last = get_last_dose_time(target_user, drug)
        if last:
            diff = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M")).total_seconds() / 3600
            if diff >= limit:
                st.error(f"🔔 {drug} is DUE ({diff:.1f}h since last dose)")
                alarm = True
    if alarm: play_alarm()

    # 4. Log Meds
    st.divider()
    st.subheader("💊 Record a New Dose")
    master = get_prescriptions(target_user)
    if not master:
        st.warning("No medications prescribed for this patient.")
    else:
        options = {}
        for n, d in master:
            l_t = get_last_dose_time(target_user, n)
            t_str = f"{(datetime.now() - datetime.strptime(l_t, '%Y-%m-%d %H:%M')).total_seconds()/3600:.1f}h ago" if l_t else "Never"
            options[f"{n} ({d}) - Last: {t_str}"] = (n, d)
        
        choice = st.selectbox("Select Med:", [""] + list(options.keys()))
        if choice:
            n, d = options[choice]
            if n == "Oxycodone" and o_tot >= 35:
                st.error("🛑 24h Limit Reached. Cannot log more.")
            elif st.button(f"Submit {n} {d}"):
                conn = sqlite3.connect('meds.db')
                c = conn.cursor()
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                c.execute('INSERT INTO medications VALUES (?,?,?,?)', (target_user, n, d, now))
                conn.commit()
                st.rerun()

    # 5. History
    st.subheader("📜 Log History")
    hist = get_meds(target_user)
    if hist:
        st.dataframe(pd.DataFrame(hist, columns=["Drug", "Dose", "Timestamp"]), use_container_width=True)

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()