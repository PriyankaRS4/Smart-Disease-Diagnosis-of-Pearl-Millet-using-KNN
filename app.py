# app.py
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify, Response
)
import os
import sqlite3
import cv2
import numpy as np
import joblib
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from generate_pdf import create_pdf
from googletrans import Translator
from datetime import datetime


# ---------------- Config ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "replace_with_a_secure_random_value"  # change before deploy
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Load your trained KNN model (ensure file exists)
model = joblib.load('model_knn.pkl')
translator = Translator()

# Disease info (simple dictionary; extend as needed)
disease_info = {
    "rust": "Rust is a fungal disease causing reddish-brown pustules on leaves.",
    "downy_mildew": "Downy mildew affects leaf surface with pale yellow spots.",
    "healthy": "The leaf is healthy with no visible signs of disease."
}

# ---------------- Database helpers ----------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        phone TEXT,
        created_at TEXT NOT NULL
    )
    """)
    conn.commit()

    # ensure admin exists
    cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password, role, phone, created_at) VALUES (?,?,?,?,?)",
            ("admin", generate_password_hash("admin123"), "admin", "", datetime.utcnow().isoformat())
        )
        conn.commit()
    conn.close()

def find_user_db(username):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row

def add_user_db(username, raw_password, role="farmer", phone=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password, role, phone, created_at) VALUES (?,?,?,?,?)",
        (username, generate_password_hash(raw_password), role, phone, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

def update_password_db(username, new_password):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password = ? WHERE username = ?",
                (generate_password_hash(new_password), username))
    conn.commit()
    conn.close()

def update_phone_db(username, phone):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET phone = ? WHERE username = ?", (phone, username))
    conn.commit()
    conn.close()

def list_farmers_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, phone, created_at FROM users WHERE role = 'farmer' ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows

# initialize DB and admin account
init_db()

# ---------------- Authentication & user flows ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role_selected = request.form.get("role", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = find_user_db(username)
        if user and check_password_hash(user["password"], password) and user["role"] == role_selected:
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Login successful", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials or wrong role selected", "danger")
    # Always render auth.html (login tab active by default)
    return render_template("auth.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()

        if not username or not password:
            flash("Username and password required", "danger")
            return redirect(url_for("register"))

        if find_user_db(username):
            flash("Username already taken", "danger")
            return redirect(url_for("register"))

        add_user_db(username, password, role="farmer", phone=phone)
        flash("Registration successful — please login", "success")
        return redirect(url_for("login"))

    # Always render auth.html (register tab active by JS)
    return render_template("auth.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "username" not in session:
        return redirect(url_for("login"))
    username = session["username"]
    user = find_user_db(username)
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        update_phone_db(username, phone)
        flash("Profile updated", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    # Only logged-in user can change their own password
    if "username" not in session:
        return redirect(url_for("login"))
    username = session["username"]
    if request.method == "POST":
        old_pw = request.form.get("old_password", "")
        new_pw = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if new_pw != confirm:
            flash("New password and confirmation do not match", "danger")
            return redirect(url_for("change_password"))

        user = find_user_db(username)
        if not user or not check_password_hash(user["password"], old_pw):
            flash("Old password is incorrect", "danger")
            return redirect(url_for("change_password"))

        update_password_db(username, new_pw)
        flash("Password changed successfully", "success")
        return redirect(url_for("profile"))

    return render_template("change_password.html")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    # Pre-login password reset via username + phone verification
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        phone = request.form.get("phone", "").strip()
        new_pw = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not phone or not new_pw:
            flash("All fields are required", "danger")
            return redirect(url_for("forgot_password"))

        if new_pw != confirm:
            flash("New password and confirmation do not match", "danger")
            return redirect(url_for("forgot_password"))

        user = find_user_db(username)
        if not user:
            flash("Username not found", "danger")
            return redirect(url_for("forgot_password"))

        stored_phone = user["phone"] or ""
        if stored_phone.strip() != phone.strip():
            flash("Phone number does not match our records", "danger")
            return redirect(url_for("forgot_password"))

        update_password_db(username, new_pw)
        flash("Password reset successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


# ---------------- Admin-only routes ----------------
@app.route("/admin_dashboard", methods=["GET", "POST"])
def admin_dashboard():
    if "username" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    farmers = list_farmers_db()

    # NOTE: By design admin MUST NOT change farmer passwords.
    # Admin can only view the farmer list (no password reset feature here).
    return render_template("admin_dashboard.html", farmers=farmers)


# ---------------- Protected detection app routes ----------------
@app.route('/')
def index():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template('index.html', diseases=list(disease_info.keys()), search_result=None)

@app.route('/upload')
def upload_page():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template('upload.html')

@app.route('/predict', methods=['POST'])
def predict():
    if "username" not in session:
        return redirect(url_for("login"))

    f = request.files['image']
    filename = str(uuid.uuid4()) + ".jpg"
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    f.save(path)

    # preprocess and predict (must match knn_train preprocessing)
    img = cv2.imread(path)
    img = cv2.resize(img, (64, 64))
    img = img / 255.0
    img = img.flatten().reshape(1, -1)

    prediction = model.predict(img)[0]
    cleaned_prediction = prediction.lower().replace("_augmented", "")
    info = disease_info.get(cleaned_prediction, "No info available.")

    try:
        proba = model.predict_proba(img)[0]
        confidence = round(float(max(proba)) * 100, 2)
    except Exception:
        confidence = "N/A"

    return render_template("result.html", image=filename, disease=prediction,
                           crop_name="Pearl Millet", info=info, confidence=confidence)
 

@app.route('/translate', methods=['POST'])
def translate_text():
    data = request.get_json()
    text = data.get('text', '')
    lang = data.get('lang', 'en')
    translated = translator.translate(text, dest=lang).text
    return jsonify({'translated': translated})

@app.route('/download_pdf/<disease>/<lang>/<confidence>/<image>')
def download_pdf(disease, lang, confidence, image):
    if "username" not in session:
        return redirect(url_for("login"))

    crop_name = "Pearl Millet"
    disease_desc = disease_info.get(disease.lower(), "No info available.")

    crop_name_t = translator.translate(crop_name, dest=lang).text
    disease_t = translator.translate(disease, dest=lang).text
    confidence_t = translator.translate(f"{confidence}%", dest=lang).text
    disease_desc_t = translator.translate(disease_desc, dest=lang).text

    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image)
    pdf_path = create_pdf(crop_name_t, disease_t, confidence_t, disease_desc_t, image_path)
    return send_file(pdf_path, as_attachment=True)

@app.route('/search', methods=['GET'])
def search():
    if "username" not in session:
        return redirect(url_for("login"))
    query = request.args.get('q', '').strip().lower()
    result = None
    if query in disease_info:
        result = {"name": query.capitalize(), "description": disease_info[query]}
    return render_template('index.html', search_result=result, diseases=list(disease_info.keys()))

# ---------------- Live Detection (Webcam) ----------------
def preprocess_frame(frame):
    frame = cv2.resize(frame, (64, 64))
    frame = frame / 255.0
    frame = frame.flatten().reshape(1, -1)
    return frame

def generate_frames():
    camera = cv2.VideoCapture(0)
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            processed = preprocess_frame(frame)
            prediction = model.predict(processed)[0]
            cleaned_prediction = prediction.lower().replace("_augmented", "")
            label = cleaned_prediction.capitalize()

            cv2.putText(frame, f"Prediction: {label}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Encode to JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    if "username" not in session:
        return redirect(url_for("login"))
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/live')
def live():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template('live.html')

# ---------------- Run ----------------
if __name__ == '__main__':
    app.run(debug=True)
