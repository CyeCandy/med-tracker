import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
# Ensure verify_user and add_med_log are in your database.py
from database import (
    init_db, add_user, get_meds, get_all_patients, 
    get_last_dose_time, add_prescription, get_prescriptions, 
    get_24hr_total, verify_user, add_med_log
)

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
                if add_user(u, p, r): 
                    st.success("Account created! Please Login.")
                else:
                    st.error("Username already exists.")
        else:
            if st.button("Sign In"):
                res = verify_user(u, p)
                if res:
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    st.session_state.role = res[0]
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    else:
        st.write(f"**User:** {st.session_state.user} ({st.session_state.role})")
        
        target_patient = st.session_state.user
        if st.session_state.role == "Clinician":
            pts = get_all_patients()
            target_patient = st.selectbox("🔍 Managing Patient:", ["-- Select Patient --"] + pts)
        
        st.divider()
        if st.button("Log Out"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# --- MAIN DASHBOARD ---
if st.session_state.logged_in:
    if st.session_state