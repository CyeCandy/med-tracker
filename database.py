import sqlite3
from datetime import datetime, timedelta

def init_db():
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS prescriptions 
                 (username TEXT, drug_name TEXT, dosage TEXT, UNIQUE(username, drug_name))''')
    c.execute('''CREATE TABLE IF NOT EXISTS medications 
                 (username TEXT, name TEXT, dosage TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

def add_prescription(username, drug, dose):
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO prescriptions VALUES (?,?,?)', (username, drug, dose))
    conn.commit()
    conn.close()

def get_prescriptions(username):
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT drug_name, dosage FROM prescriptions WHERE username=?', (username,))
    data = c.fetchall()
    conn.close()
    return data

def add_user(username, password, role="Patient"):
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users VALUES (?,?,?)', (username, password, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False 
    finally:
        conn.close()

def get_meds(username):
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT name, dosage, timestamp FROM medications WHERE username=? ORDER BY timestamp DESC', (username,))
    data = c.fetchall()
    conn.close()
    return data

def get_all_patients():
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE role='Patient'")
    patients = [row[0] for row in c.fetchall()]
    conn.close()
    return patients

def get_last_dose_time(username, drug_name=None):
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    if drug_name:
        c.execute('SELECT timestamp FROM medications WHERE username=? AND name=? ORDER BY timestamp DESC LIMIT 1', (username, drug_name))
    else:
        c.execute('SELECT timestamp FROM medications WHERE username=? ORDER BY timestamp DESC LIMIT 1', (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_24hr_total(username, drug_name):
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
    c.execute('SELECT dosage FROM medications WHERE username=? AND name=? AND timestamp > ?', (username, drug_name, since))
    doses = c.fetchall()
    conn.close()
    total = 0.0
    for d in doses:
        try:
            # Cleans "7 ml" or "4 ml" into a float
            clean_val = d[0].lower().replace('ml', '').replace('mg', '').strip()
            total += float(clean_val)
        except:
            continue
    return total