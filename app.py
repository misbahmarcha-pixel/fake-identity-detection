"""
app.py
------
Fake Identity Detection Platform — full application.

Routes:
  /                    Landing/home page
  /signup              Create account (name/email/phone/username/password)
  /login               User login
  /logout              Clear user session
  /register            Multi-step verification wizard (requires login)
  /send-otp            AJAX: generate + return OTP (demo mode, no real SMTP configured)
  /verify-otp          AJAX: check submitted OTP against session
  /generate-sample-id  AJAX: returns a checksum-valid test Aadhaar number (demo helper)
  /submit-registration POST: runs full verification pipeline -> redirect to result
  /result/<id>         Verification result (QR, confidence, PDF-printable)
  /profile             My verification history (logged-in user)
  /admin/login         Admin login (password protected)
  /admin/logout        Clear admin session
  /dashboard           Admin dashboard: charts, search/filter, activity log
  /api/stats           JSON stats for dashboard charts
"""

import os
import random
import datetime
from functools import wraps
from flask import (
    Flask, request, render_template, redirect, url_for, session, jsonify, flash
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    init_db, insert_user, get_all_users, get_user_by_id, get_history_by_email,
    get_decision_stats, log_activity, get_activity_log,
    create_auth_user, get_auth_user_by_username, get_auth_user_by_id,
)
from decision_engine import evaluate_registration
from id_verification import generate_valid_aadhaar

app = Flask(__name__)
app.secret_key = "udp-project-demo-secret-key"  # fine for a student demo; not for real deployment
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_PASSWORD = "admin123"  # change this before any real deployment

init_db()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("auth_user_id"):
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
@app.route("/")
def home():
    stats = get_decision_stats()
    total = sum(stats["by_decision"].values()) if stats["by_decision"] else 0
    return render_template("home.html", total=total, by_decision=stats["by_decision"])


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not all([name, email, phone, username, password]):
            error = "Please fill in all fields."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            pw_hash = generate_password_hash(password)
            new_id, err = create_auth_user(name, email, phone, username, pw_hash)
            if err:
                error = err
            else:
                session["auth_user_id"] = new_id
                session["auth_user_name"] = name
                session["auth_user_email"] = email
                log_activity("signup", f"New account: {username} ({email})")
                flash("Account created. Let's verify your identity next.", "success")
                return redirect(url_for("register"))

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_auth_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["auth_user_id"] = user["id"]
            session["auth_user_name"] = user["name"]
            session["auth_user_email"] = user["email"]
            log_activity("login", f"{username} logged in")
            return redirect(url_for("home"))
        error = "Incorrect username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("auth_user_id", None)
    session.pop("auth_user_name", None)
    session.pop("auth_user_email", None)
    return redirect(url_for("home"))


@app.route("/register")
@login_required
def register():
    return render_template("register.html",
                            auth_name=session.get("auth_user_name"),
                            auth_email=session.get("auth_user_email"))


# --- OTP (demo mode: no real email server configured, OTP is shown directly
#     on screen with a clear label so the flow can still be demonstrated) ---
@app.route("/send-otp", methods=["POST"])
def send_otp():
    email = request.json.get("email", "").strip()
    otp = f"{random.randint(100000, 999999)}"
    session["otp_email"] = email
    session["otp_code"] = otp
    session["otp_time"] = datetime.datetime.now().isoformat()
    return jsonify({"status": "sent", "demo_otp": otp, "email": email})


@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    submitted = request.json.get("otp", "").strip()
    valid = submitted and submitted == session.get("otp_code")
    return jsonify({"valid": bool(valid)})


@app.route("/generate-sample-id")
def generate_sample_id():
    """Demo convenience: returns a checksum-valid test Aadhaar number so
    users can see the 'Verified' path without hand-crafting a valid number."""
    return jsonify({"id_number": generate_valid_aadhaar()})


@app.route("/submit-registration", methods=["POST"])
@login_required
def submit_registration():
    form = request.form
    doc_file = request.files.get("document")
    selfie_file = request.files.get("selfie")

    doc_filename = secure_filename(doc_file.filename)
    doc_path = os.path.join(app.config["UPLOAD_FOLDER"], doc_filename)
    doc_file.save(doc_path)

    selfie_path = None
    if selfie_file and selfie_file.filename:
        selfie_filename = secure_filename(selfie_file.filename)
        selfie_path = os.path.join(app.config["UPLOAD_FOLDER"], selfie_filename)
        selfie_file.save(selfie_path)

    form_data = {
        "name": session.get("auth_user_name", ""),
        "email": session.get("auth_user_email", ""),
        "phone": form.get("phone", ""),
        "username": form.get("username", ""),
        "bio": form.get("bio", ""),
        "has_profile_picture": bool(form.get("has_profile_picture")),
        "doc_type": form.get("doc_type", "aadhaar"),
        "id_number": form.get("id_number", ""),
        "dob": form.get("dob", ""),
        "ip_address": form.get("ip_address") or request.remote_addr or "0.0.0.0",
        "device_id": form.get("device_id", "UNKNOWN-DEVICE"),
    }

    result = evaluate_registration(form_data, doc_path, selfie_path)

    qr_payload = f"VERIFY:{form_data['name']}:{form_data['email']}:{result['decision']}"

    user_id = insert_user(
        name=form_data["name"], email=form_data["email"], phone=form_data["phone"],
        username=form_data["username"], ip_address=form_data["ip_address"],
        device_id=form_data["device_id"],
        created_at=datetime.datetime.now().isoformat(timespec="seconds"),
        decision=result["decision"], final_risk_score=result["final_risk_score"],
        reasons="; ".join(result["reasons"]),
        ai_confidence=result["ai_confidence"],
        selfie_face_detected=1 if result["selfie_result"]["face_detected"] else 0,
        qr_payload=qr_payload,
    )

    return jsonify({"redirect": url_for("show_result", user_id=user_id)})


@app.route("/result/<int:user_id>")
def show_result(user_id):
    user = get_user_by_id(user_id)
    reasons = user["reasons"].split("; ") if user["reasons"] else []
    return render_template("result.html", user=user, reasons=reasons)


@app.route("/profile")
def profile():
    email = request.args.get("email", "").strip() or session.get("auth_user_email", "")
    history = get_history_by_email(email) if email else []
    return render_template("profile.html", email=email, history=history)


# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            log_activity("admin_login", "Admin logged in")
            return redirect(url_for("dashboard"))
        error = "Incorrect password."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("home"))


@app.route("/dashboard")
@admin_required
def dashboard():
    search = request.args.get("search", "")
    decision_filter = request.args.get("decision", "")
    users = get_all_users(search=search, decision_filter=decision_filter)
    logs = get_activity_log(30)
    return render_template("dashboard.html", users=users, logs=logs,
                            search=search, decision_filter=decision_filter)


@app.route("/api/stats")
@admin_required
def api_stats():
    return jsonify(get_decision_stats())


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)
