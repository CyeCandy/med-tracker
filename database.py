import sqlite3
import hashlib
from datetime import datetime, timedelta

DB_NAME = 'meds.db'

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)')
        c.execute('''CREATE TABLE IF NOT EXISTS prescriptions 
                     (username TEXT, drug_name TEXT, dosage TEXT, UNIQUE(username, drug_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS medications 
                     (username TEXT, name TEXT, dosage TEXT, timestamp DATETIME, logged_by TEXT)''')
        conn.commit()

def add_user(username, password, role="Patient"):
    hashed = hash_password(password)
    try:
        with get_connection() as conn:
            conn.execute('INSERT INTO users VALUES (?,?,?)', (username, hashed, role))
            return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username, password):
    hashed = hash_password(password)
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT role FROM users WHERE username=? AND password=?', (username, hashed))
        return c.fetchone()

def add_prescription(username, drug, dose):
    with get_connection() as conn:
        conn.execute('INSERT OR REPLACE INTO prescriptions VALUES (?,?,?)', (username, drug, dose))

def get_prescriptions(username):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT drug_name, dosage FROM prescriptions WHERE username=?', (username,))
        return c.fetchall()

def add_med_log(patient_name, drug_name, dosage, admin_by):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_connection() as conn:
        conn.execute('INSERT INTO medications VALUES (?,?,?,?,?)', (patient_name, drug_name, dosage, now, admin_by))

def get_meds(username):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT name, dosage, timestamp, logged_by FROM medications WHERE username=? ORDER BY timestamp DESC', (username,))
        return c.fetchall()

def get_all_patients():
    with get_connection() as conn:
        c = conn.cursor()
        # CRITICAL: Only pull users who are registered as 'Patient'
        c.execute("SELECT username FROM users WHERE role='Patient'")
        return [row[0] for row in c.fetchall()]

def get_last_dose_time(username, drug_name=None):
    with get_connection() as conn:
        c = conn.cursor()
        if drug_name:
            c.execute('SELECT timestamp FROM medications WHERE username=? AND name=? ORDER BY timestamp DESC LIMIT 1', (username, drug_name))
        else:
            c.execute('SELECT timestamp FROM medications WHERE username=? ORDER BY timestamp DESC LIMIT 1', (username,))
        res = c.fetchone()
        return res[0] if res else None

def get_24hr_total(username, drug_name):
    with get_connection() as conn:
        c = conn.cursor()
        since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
        c.execute('SELECT dosage FROM medications WHERE username=? AND name=? AND timestamp > ?', (username, drug_name, since))
        doses = c.fetchall()
    total = 0.0
    for d in doses:
        try:
            val = "".join(filter(lambda x: x.isdigit() or x == '.', d[0]))
            total += float(val)
        except: continue
    return total