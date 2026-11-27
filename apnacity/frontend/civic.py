from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import mysql.connector
from mysql.connector import Error
import os
import re
import threading
import uuid
import webbrowser
from html import escape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load settings from the .env file next to civic.py (if python-dotenv is installed)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    print("Tip: run 'pip install python-dotenv' to load settings from .env")
app = Flask(__name__, static_folder=None)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024   # 5 MB upload limit
CORS(app)

SECRET_KEY = os.getenv("JWT_SECRET", "CIVICAI_SECRET_KEY_CHANGE_THIS")
ALLOW_ADMIN_SIGNUP = os.getenv("ALLOW_ADMIN_SIGNUP", "false").lower() == "true"
DB_NAME = os.getenv("DB_NAME", "apnacity")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"  # true on HTTPS hosting
DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
# true = only admins can upload Verified Impact photos; false = any logged-in user
IMPACT_ADMIN_ONLY = os.getenv("IMPACT_ADMIN_ONLY", "false").lower() == "true"


# ==============================
# DATABASE
# ==============================

def db_config(with_database=True):
    cfg = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
    if with_database:
        cfg["database"] = DB_NAME
    return cfg


def get_db():
    try:
        return mysql.connector.connect(**db_config())
    except Error as e:
        print(f"Database Error: {e}")
        return None


def init_db():
    """Create the database and tables if they don't exist yet."""
    try:
        try:
            # Hosted MySQL: the database is created in the host's dashboard
            conn = mysql.connector.connect(**db_config())
            cur = conn.cursor()
        except Error:
            # Local MySQL: create the database if it doesn't exist yet
            conn = mysql.connector.connect(**db_config(with_database=False))
            cur = conn.cursor()
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
            cur.execute(f"USE `{DB_NAME}`")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'citizen',
                full_name VARCHAR(150),
                street VARCHAR(255),
                postal_code VARCHAR(20),
                city VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS civic_complaints (
                Complaint_ID VARCHAR(40) PRIMARY KEY,
                City VARCHAR(100),
                Area_Locality VARCHAR(150),
                Zone VARCHAR(100),
                Latitude DECIMAL(10,6) NULL,
                Longitude DECIMAL(10,6) NULL,
                Issue TEXT,
                Category VARCHAR(100),
                Responsible_Authority VARCHAR(150),
                Severity VARCHAR(20),
                AI_Confidence DECIMAL(4,2),
                Citizen_Support_Count INT DEFAULT 0,
                NGO_Involved VARCHAR(5),
                Citizen_Group_Active VARCHAR(5),
                Complaint_Status VARCHAR(30),
                Days_Open INT DEFAULT 0,
                AI_Auto_Routed VARCHAR(5),
                Evidence VARCHAR(255),
                Resolution_Verified VARCHAR(5),
                Priority_Score INT,
                User_ID INT NULL,
                Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add User_ID to an older table that was created without it
        cur.execute("SHOW COLUMNS FROM civic_complaints LIKE 'User_ID'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE civic_complaints ADD COLUMN User_ID INT NULL")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS impact_images (
                slot VARCHAR(10) PRIMARY KEY,
                image_url VARCHAR(255) NOT NULL,
                uploaded_by INT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Database ready.")
        return True
    except Error as e:
        print(f"Could not initialise database: {e}")
        return False


# ==============================
# HELPERS
# ==============================

def get_input():
    """Accept JSON or normal HTML form data."""
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return data
    if request.form:
        return request.form.to_dict()
    return {}


def is_form_post():
    return not request.is_json and bool(request.form)


def login_redirect(token, target="/index.html"):
    resp = redirect(target)
    resp.set_cookie("token", token, max_age=86400, httponly=True,
                    samesite="Lax", secure=COOKIE_SECURE)
    return resp


def json_with_cookie(body, status, token):
    resp = jsonify(body)
    resp.status_code = status
    resp.set_cookie("token", token, max_age=86400, httponly=True,
                    samesite="Lax", secure=COOKIE_SECURE)
    return resp


def form_error(message, back):
    return (f"<h3>{escape(message)}</h3><p><a href='{back}'>Go back</a></p>", 400)


def to_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def verify_token():
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        token = parts[1]
    else:
        token = request.cookies.get("token")
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def create_token(user_id, email, role):
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token.decode() if isinstance(token, bytes) else token


# ==============================
# AI CATEGORY / DEPARTMENT DETECTION
# ==============================

CATEGORY_KEYWORDS = [
    ("waste", "Waste Management"),
    ("garbage", "Waste Management"),
    ("trash", "Waste Management"),
    ("pothole", "Road Damage"),
    ("road", "Road Damage"),
    ("water", "Water Supply"),
    ("drain", "Drainage"),
    ("sewer", "Drainage"),
    ("sewage", "Drainage"),
    ("streetlight", "Street Light"),
    ("street light", "Street Light"),
    ("light", "Street Light"),
    ("pollution", "Pollution"),
    ("smoke", "Pollution"),
    ("animal", "Animal"),
    ("dog", "Animal"),
    ("cattle", "Animal"),
    ("tree", "Environment"),
    ("traffic", "Traffic"),
]

DEPARTMENTS = {
    "Waste Management": "Municipal Corporation",
    "Road Damage": "Public Works Department",
    "Water Supply": "Water Department",
    "Drainage": "Drainage Department",
    "Street Light": "Electrical Department",
    "Pollution": "Pollution Control Board",
    "Animal": "Animal Welfare Department",
    "Environment": "Environment Department",
    "Traffic": "Traffic Police",
}


def detect_category(text):
    # Whole-word matching, so "street" no longer matches "tree"
    # and "flight" no longer matches "light".
    text = text.lower()
    for word, category in CATEGORY_KEYWORDS:
        if re.search(rf"\b{re.escape(word)}s?\b", text):
            return category
    return "Other"


def detect_department(category):
    return DEPARTMENTS.get(category, "Municipal Corporation")


def ai_analyze_issue(description):
    category = detect_category(description)
    return {
        "issue": description,
        "category": category,
        "responsible_authority": detect_department(category),
        "severity": "Medium",
        "ai_confidence": 0.8,
        "priority_score": 50,
    }


# ==============================
# AUTH ROUTES
# ==============================

@app.route("/signup", methods=["POST"])
def signup():
    data = get_input()

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        if is_form_post():
            return form_error("Valid email is required", "/signin.html")
        return jsonify({"success": False, "message": "Valid email is required"}), 400
    if len(password) < 6:
        if is_form_post():
            return form_error("Password must be at least 6 characters", "/signin.html")
        return jsonify({"success": False,
                        "message": "Password must be at least 6 characters"}), 400

    wants_admin = str(data.get("isAdmin", "")).lower() in ("true", "on", "1")
    role = "admin" if (wants_admin and ALLOW_ADMIN_SIGNUP) else "citizen"

    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"}), 500

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            if is_form_post():
                return form_error("Email already registered", "/signin.html")
            return jsonify({"success": False,
                            "message": "Email already registered"}), 409

        cursor.execute(
            """INSERT INTO users
               (email, password_hash, role, full_name, street, postal_code, city)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                email,
                generate_password_hash(password),
                role,
                data.get("Fullname") or data.get("full_name"),
                data.get("street"),
                data.get("postalcode"),
                data.get("city"),
            ),
        )
        conn.commit()
        user_id = cursor.lastrowid

        if is_form_post():
            return login_redirect(create_token(user_id, email, role))

        token = create_token(user_id, email, role)
        return json_with_cookie({
            "success": True,
            "message": "Account created successfully",
            "token": token,
            "role": role,
        }, 201, token)

    except Error as e:
        conn.rollback()
        print(f"Signup Error: {e}")
        return jsonify({"success": False, "message": "Unable to create account"}), 500
    finally:
        if cursor:
            cursor.close()
        conn.close()


@app.route("/login", methods=["POST"])
def login():
    data = get_input()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"success": False,
                        "message": "Email and password are required"}), 400

    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"}), 500

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, password_hash, role FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()

        if not row or not check_password_hash(row[1], password):
            if is_form_post():
                return form_error("Invalid email or password", "/login.html")
            return jsonify({"success": False,
                            "message": "Invalid email or password"}), 401

        if is_form_post():
            return login_redirect(create_token(row[0], email, row[2]))

        token = create_token(row[0], email, row[2])
        return json_with_cookie({
            "success": True,
            "message": "Login successful",
            "token": token,
            "role": row[2],
        }, 200, token)
    except Error as e:
        print(f"Login Error: {e}")
        return jsonify({"success": False, "message": "Login failed"}), 500
    finally:
        if cursor:
            cursor.close()
        conn.close()


# ==============================
# REPORT ROUTES
# ==============================

@app.route("/api/reports", methods=["POST"])
def create_report():
    payload = verify_token()
    if not payload:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    data = get_input()

    description = data.get("issue") or data.get("description") or data.get("Issue")
    if not isinstance(description, str) or not description.strip():
        return jsonify({"success": False,
                        "message": "Issue description is required"}), 400
    description = description.strip()

    analysis = ai_analyze_issue(description)

    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"}), 500

    cursor = None
    try:
        cursor = conn.cursor()
        complaint_id = f"CIV-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        query = """
            INSERT INTO civic_complaints (
                Complaint_ID, City, Area_Locality, Zone, Latitude, Longitude,
                Issue, Category, Responsible_Authority, Severity, AI_Confidence,
                Citizen_Support_Count, NGO_Involved, Citizen_Group_Active,
                Complaint_Status, Days_Open, AI_Auto_Routed, Evidence,
                Resolution_Verified, Priority_Score, User_ID
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            complaint_id,
            data.get("city"),
            data.get("area_locality") or data.get("Area"),
            data.get("zone"),
            to_float(data.get("latitude")),
            to_float(data.get("longitude")),
            analysis["issue"],
            analysis["category"],
            analysis["responsible_authority"],
            analysis["severity"],
            analysis["ai_confidence"],
            0, "No", "No", "Pending", 0, "Yes",
            data.get("evidence", "None"),
            "No",
            analysis["priority_score"],
            payload["user_id"],
        )

        cursor.execute(query, values)
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Report submitted successfully",
            "complaint_id": complaint_id,
            "analysis": analysis,
        }), 201

    except Error as e:
        conn.rollback()
        print(f"Report Submission Error: {e}")
        return jsonify({"success": False, "message": "Unable to submit report"}), 500
    finally:
        if cursor:
            cursor.close()
        conn.close()


@app.route("/api/reports", methods=["GET"])
def list_reports():
    """Complaints of the logged-in user (admins see all)."""
    payload = verify_token()
    if not payload:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"}), 500

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cols = """Complaint_ID, City, Area_Locality, Issue, Category,
                  Responsible_Authority, Severity, Complaint_Status,
                  Days_Open, Resolution_Verified, Priority_Score, Created_At"""
        if payload.get("role") == "admin":
            cursor.execute(f"SELECT {cols} FROM civic_complaints ORDER BY Created_At DESC")
        else:
            cursor.execute(
                f"SELECT {cols} FROM civic_complaints WHERE User_ID = %s "
                "ORDER BY Created_At DESC", (payload["user_id"],))
        return jsonify({"success": True, "reports": cursor.fetchall()})
    except Error as e:
        print(f"List Error: {e}")
        return jsonify({"success": False, "message": "Unable to fetch reports"}), 500
    finally:
        if cursor:
            cursor.close()
        conn.close()


@app.route("/api/reports/<complaint_id>", methods=["GET"])
def track_report(complaint_id):
    payload = verify_token()
    if not payload:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"}), 500

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT Complaint_ID, City, Area_Locality, Issue, Category,
                      Responsible_Authority, Severity, Complaint_Status,
                      Days_Open, Resolution_Verified, Priority_Score, User_ID
               FROM civic_complaints WHERE Complaint_ID = %s""",
            (complaint_id,),
        )
        row = cursor.fetchone()
        if not row or (payload.get("role") != "admin"
                       and row["User_ID"] != payload["user_id"]):
            return jsonify({"success": False, "message": "Report not found"}), 404
        row.pop("User_ID", None)
        return jsonify({"success": True, "report": row})
    except Error as e:
        print(f"Track Error: {e}")
        return jsonify({"success": False, "message": "Unable to fetch report"}), 500
    finally:
        if cursor:
            cursor.close()
        conn.close()


@app.route("/api/me", methods=["GET"])
def me():
    """Who is logged in? Used by auth.js to protect pages and show Logout."""
    payload = verify_token()
    if not payload:
        return jsonify({"success": False, "message": "Not logged in"}), 401
    return jsonify({"success": True, "email": payload["email"], "role": payload["role"]})


@app.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        resp = jsonify({"success": True, "message": "Logged out"})
    else:
        resp = redirect("/login.html")
    resp.delete_cookie("token")
    return resp


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"success": True, "message": "ApnaCity Civic API is running"})


# ==============================
# VERIFIED IMPACT: PHOTO UPLOAD
# ==============================

def detect_image_type(head):
    """Check the file's real content (not just its name). Returns an extension or None."""
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


@app.errorhandler(413)
def file_too_large(e):
    return jsonify({"success": False, "message": "File is too large (maximum 5 MB)"}), 413


@app.route("/api/impact", methods=["GET"])
def impact_images():
    """Current BEFORE / AFTER photos for the Verified Impact page."""
    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"}), 500
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT slot, image_url FROM impact_images")
        images = {slot: url for slot, url in cursor.fetchall()}
        return jsonify({"success": True, "images": images})
    except Error as e:
        print(f"Impact Error: {e}")
        return jsonify({"success": False, "message": "Unable to load images"}), 500
    finally:
        if cursor:
            cursor.close()
        conn.close()


@app.route("/api/impact/upload", methods=["POST"])
def impact_upload():
    payload = verify_token()
    if not payload:
        return jsonify({"success": False, "message": "Please log in to upload"}), 401
    if IMPACT_ADMIN_ONLY and payload.get("role") != "admin":
        return jsonify({"success": False, "message": "Only admins can upload"}), 403

    slot = request.form.get("slot", "")
    if slot not in ("before", "after"):
        return jsonify({"success": False, "message": "Slot must be before or after"}), 400

    file = request.files.get("photo")
    if not file or not file.filename:
        return jsonify({"success": False, "message": "No file selected"}), 400

    ext = detect_image_type(file.read(16))
    file.seek(0)
    if not ext:
        return jsonify({"success": False,
                        "message": "Only JPG, PNG, GIF or WEBP images are allowed"}), 400

    # random name, so nobody can overwrite or guess other files
    filename = f"{slot}-{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    conn = get_db()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"}), 500

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT image_url FROM impact_images WHERE slot = %s", (slot,))
        old = cursor.fetchone()

        file.save(path)
        url = f"uploads/{filename}"
        cursor.execute(
            """INSERT INTO impact_images (slot, image_url, uploaded_by)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE image_url = VALUES(image_url),
                                       uploaded_by = VALUES(uploaded_by)""",
            (slot, url, payload["user_id"]),
        )
        conn.commit()

        # remove the replaced photo from disk
        if old and old[0].startswith("uploads/"):
            old_path = os.path.join(UPLOAD_DIR, os.path.basename(old[0]))
            if os.path.exists(old_path):
                os.remove(old_path)

        return jsonify({"success": True, "message": "Photo uploaded", "url": url})
    except (Error, OSError) as e:
        conn.rollback()
        if os.path.exists(path):
            os.remove(path)
        print(f"Upload Error: {e}")
        return jsonify({"success": False, "message": "Unable to save photo"}), 500
    finally:
        if cursor:
            cursor.close()
        conn.close()


# ==============================
# SERVE THE WEBSITE (HTML + images)
# ==============================

ALLOWED_EXT = (".html", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".css", ".js", ".ico")


@app.route("/", methods=["GET"])
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/login", methods=["GET"])
def login_page():
    return redirect("/login.html")


@app.route("/signup", methods=["GET"])
def signup_page():
    return redirect("/signin.html")


@app.route("/<path:filename>", methods=["GET"])
def site_files(filename):
    # only serve website files, never civic.py / req.txt
    if not filename.lower().endswith(ALLOWED_EXT):
        return jsonify({"success": False, "message": "Not found"}), 404
    return send_from_directory(BASE_DIR, filename)


# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    if SECRET_KEY == "CIVICAI_SECRET_KEY_CHANGE_THIS":
        print("WARNING: using the default JWT secret. Set JWT_SECRET before deploying.")

    if not init_db():
        print("Database not available - pages will open, but login/report will fail "
              "until MySQL is running and DB_PASSWORD is set.")

    URL = "http://127.0.0.1:5000/"
    print(f"Opening {URL} in your browser...")
    threading.Timer(1.2, lambda: webbrowser.open(URL)).start()

    # use_reloader=False so the browser opens only once
    app.run(host="127.0.0.1", port=5000, debug=DEBUG, use_reloader=False)
