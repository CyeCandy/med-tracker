import sqlite3

def init_db():
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS medications 
                 (username TEXT, name TEXT, dosage TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

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

def get_last_dose_time(username):
    conn = sqlite3.connect('meds.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT timestamp FROM medications WHERE username=? ORDER BY timestamp DESC LIMIT 1', (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None