"""
database.py
------------
Sets up the SQLite database used by the platform (swap the connection
in a real deployment to MySQL via SQLAlchemy — schema stays identical).

Table: users
  Stores every registered account so we can detect duplicates: same email,
  phone, IP address, or device fingerprint reused across "different" accounts.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "identity_platform.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    username TEXT,
    ip_address TEXT,
    device_id TEXT,
    account_created_at TEXT,
    is_flagged INTEGER DEFAULT 0,
    decision TEXT DEFAULT 'Verified',
    final_risk_score REAL DEFAULT 0,
    reasons TEXT DEFAULT '',
    ai_confidence REAL DEFAULT 0,
    selfie_face_detected INTEGER DEFAULT 0,
    qr_payload TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT,
    detail TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS auth_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    phone TEXT,
    username TEXT UNIQUE,
    password_hash TEXT,
    created_at TEXT
);
"""

# Sample "existing" users already in the system — a realistic mix of genuine
# accounts and a few fraud-pattern accounts (shared IP/device, disposable
# email) so duplicate detection has something to actually catch in the demo.
SEED_USERS = [
    ("Aarav Patel", "aarav.patel92@gmail.com", "9825612345", "aarav_p", "103.21.44.10", "DEV-A1F9", "2025-11-02", 0),
    ("Priya Shah", "priya.shah@yahoo.com", "9909988776", "priyashah", "103.21.44.11", "DEV-B2C1", "2025-12-15", 0),
    ("Rohan Mehta", "rohan.mehta@outlook.com", "9825511223", "rohanm", "182.71.9.5", "DEV-C3D2", "2026-01-20", 0),
    ("Sneha Joshi", "sneha.j@gmail.com", "9898123456", "snehaj99", "182.71.9.6", "DEV-D4E3", "2026-02-10", 0),
    # Fraud-pattern accounts: same IP + device reused for "different" identities
    ("Rahul Kumar", "rahul.k.9273@tempmail.com", "9000000001", "xk29fh3kd", "45.33.12.200", "DEV-X9Z1", "2026-06-01", 1),
    ("Rahul K", "rahulk8823@10minutemail.com", "9000000002", "rk8823xz", "45.33.12.200", "DEV-X9Z1", "2026-06-02", 1),
    ("Amit Singh", "amit.singh@mailinator.com", "9111111111", "amitsingh01", "45.33.12.200", "DEV-X9Z1", "2026-06-03", 1),
]


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db(reset: bool = False):
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        for row in SEED_USERS:
            name, email, phone, username, ip, device, created, is_flagged = row
            decision = "Rejected" if is_flagged else "Verified"
            cur.execute(
                "INSERT INTO users (name, email, phone, username, ip_address, device_id, "
                "account_created_at, is_flagged, decision, final_risk_score, ai_confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, email, phone, username, ip, device, created, is_flagged, decision,
                 88.0 if is_flagged else 8.0, 90.0),
            )
    conn.commit()
    conn.close()


def insert_user(name, email, phone, username, ip_address, device_id, created_at,
                 decision="Verified", final_risk_score=0.0, reasons="",
                 ai_confidence=0.0, selfie_face_detected=0, qr_payload=""):
    conn = get_connection()
    cur = conn.cursor()
    is_flagged = 1 if decision != "Verified" else 0
    cur.execute(
        "INSERT INTO users (name, email, phone, username, ip_address, device_id, "
        "account_created_at, is_flagged, decision, final_risk_score, reasons, "
        "ai_confidence, selfie_face_detected, qr_payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, email, phone, username, ip_address, device_id, created_at,
         is_flagged, decision, final_risk_score, reasons,
         ai_confidence, selfie_face_detected, qr_payload),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    log_activity("registration", f"{name} ({email}) -> {decision}")
    return new_id


def get_all_users(flagged_only: bool = False, search: str = "", decision_filter: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    query = ("SELECT id, name, email, phone, decision, final_risk_score, reasons, "
              "account_created_at, ai_confidence FROM users WHERE 1=1")
    params = []
    if flagged_only:
        query += " AND is_flagged = 1"
    if search:
        query += " AND (name LIKE ? OR email LIKE ? OR phone LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    if decision_filter:
        query += " AND decision = ?"
        params.append(decision_filter)
    query += " ORDER BY id DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_by_id(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.close()
    return dict(zip(cols, row)) if row else None


def get_history_by_email(email: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ? ORDER BY id DESC", (email,))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


def get_decision_stats():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT decision, COUNT(*) FROM users GROUP BY decision")
    rows = dict(cur.fetchall())
    cur.execute("SELECT final_risk_score FROM users")
    scores = [r[0] for r in cur.fetchall()]
    conn.close()
    return {"by_decision": rows, "risk_scores": scores}


def log_activity(event: str, detail: str):
    import datetime
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO activity_log (event, detail, created_at) VALUES (?, ?, ?)",
                (event, detail, datetime.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


def get_activity_log(limit: int = 50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT event, detail, created_at FROM activity_log ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def find_by_field(field: str, value: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT id, name, email, phone, ip_address, device_id FROM users WHERE {field} = ?", (value,))
    rows = cur.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    init_db(reset=True)
    print(f"Database created at {DB_PATH} with {len(SEED_USERS)} seed users.")


def create_auth_user(name, email, phone, username, password_hash):
    import datetime
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO auth_users (name, email, phone, username, password_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, phone, username, password_hash,
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id, None
    except sqlite3.IntegrityError:
        conn.close()
        return None, "Username or email already registered."


def get_auth_user_by_username(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM auth_users WHERE username = ?", (username,))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.close()
    return dict(zip(cols, row)) if row else None


def get_auth_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM auth_users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.close()
    return dict(zip(cols, row)) if row else None
