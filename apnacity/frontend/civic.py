
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
import webbrowser

# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    print("Install python-dotenv: pip install python-dotenv")

app = Flask(__name__, static_folder=None)
CORS(app)

SECRET_KEY = os.getenv("JWT_SECRET", "CHANGE_THIS_SECRET")
DB_NAME = os.getenv("DB_NAME", "apnacity")
ALLOW_ADMIN_SIGNUP = os.getenv("ALLOW_ADMIN_SIGNUP", "false").lower() == "true"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"


# ==========================================
# DATABASE CONNECTION
# ==========================================

def db_config(with_database=True):
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "port": int(os.getenv("DB_PORT", "3306")),
    }

    if with_database:
        config["database"] = DB_NAME

    return config


def get_db():
    try:
        conn = mysql.connector.connect(**db_config())

        if conn.is_connected():
            print("MySQL Database Connected Successfully!")

        return conn

    except Error as e:
        print("Database Connection Error:", e)
        return None


def init_db():
    conn = None
    cursor = None

    try:
        try:
            conn = mysql.connector.connect(**db_config())
        except Error:
            conn = mysql.connector.connect(**db_config(False))
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
            cursor.execute(f"USE `{DB_NAME}`")

        if cursor is None:
            cursor = conn.cursor()

        cursor.execute("""
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS civic_complaints (
                Complaint_ID VARCHAR(40) PRIMARY KEY,
                City VARCHAR(100),
                Area_Locality VARCHAR(150),
                Zone VARCHAR(100),
                Latitude DECIMAL(10,6),
                Longitude DECIMAL(10,6),
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

        cursor.execute(
            "SHOW COLUMNS FROM civic_complaints LIKE 'User_ID'"
        )

        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE civic_complaints ADD COLUMN User_ID INT NULL"
            )

        conn.commit()
        print("Database and tables are ready!")
        return True

    except Error as e:
        print("Database Initialisation Error:", e)
        return False

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_input():
    data = request.get_json(silent=True)

    if isinstance(data, dict):
        return data

    if request.form:
        return request.form.to_dict()

    return {}


def is_form_post():
    return not request.is_json and bool(request.form)


def create_token(user_id, email, role):
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


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
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None


def set_token_cookie(response, token):
    response.set_cookie(
        "token",
        token,
        max_age=86400,
        httponly=True,
        samesite="Lax",
        secure=COOKIE_SECURE
    )
    return response


def login_redirect(token):
    response = redirect("/index.html")
    return set_token_cookie(response, token)


def json_with_cookie(data, status, token):
    response = jsonify(data)
    response.status_code = status
    return set_token_cookie(response, token)


def form_error(message, back):
    return (
        f"<h3>{message}</h3><p><a href='{back}'>Go back</a></p>",
        400
    )


def to_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (ValueError, TypeError):
        return None


# ==========================================
# AI CATEGORY DETECTION
# ==========================================

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
    ("traffic", "Traffic")
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
    "Traffic": "Traffic Police"
}


def detect_category(description):
    description = description.lower()

    for word, category in CATEGORY_KEYWORDS:
        if re.search(rf"\b{re.escape(word)}s?\b", description):
            return category

    return "Other"


def ai_analyze_issue(description):
    category = detect_category(description)

    return {
        "issue": description,
        "category": category,
        "responsible_authority": DEPARTMENTS.get(
            category, "Municipal Corporation"
        ),
        "severity": "Medium",
        "ai_confidence": 0.8,
        "priority_score": 50
    }


# ==========================================
# SIGNUP
# ==========================================

@app.route("/signup", methods=["POST"])
def signup():

    data = get_input()

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not re.match(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email
    ):
        return jsonify({
            "success": False,
            "message": "Valid email is required"
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must be at least 6 characters"
        }), 400

    wants_admin = str(data.get("isAdmin", "")).lower() in (
        "true", "on", "1"
    )

    role = (
        "admin"
        if wants_admin and ALLOW_ADMIN_SIGNUP
        else "citizen"
    )

    conn = get_db()

    if not conn:
        return jsonify({
            "success": False,
            "message": "Database connection failed"
        }), 500

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Email already registered"
            }), 409

        cursor.execute("""
            INSERT INTO users
            (email, password_hash, role, full_name,
             street, postal_code, city)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            email,
            generate_password_hash(password),
            role,
            data.get("Fullname") or data.get("full_name"),
            data.get("street"),
            data.get("postalcode"),
            data.get("city")
        ))

        conn.commit()

        user_id = cursor.lastrowid
        token = create_token(user_id, email, role)

        if is_form_post():
            return login_redirect(token)

        return json_with_cookie({
            "success": True,
            "message": "Account created successfully",
            "token": token,
            "role": role
        }, 201, token)

    except Error as e:
        conn.rollback()
        print("Signup Error:", e)

        return jsonify({
            "success": False,
            "message": "Unable to create account"
        }), 500

    finally:
        if cursor:
            cursor.close()
        conn.close()


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["POST"])
def login():

    data = get_input()

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    conn = get_db()

    if not conn:
        return jsonify({
            "success": False,
            "message": "Database connection failed"
        }), 500

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, password_hash, role
            FROM users
            WHERE email = %s
        """, (email,))

        row = cursor.fetchone()

        if not row or not check_password_hash(row[1], password):

            if is_form_post():
                return form_error(
                    "Invalid email or password",
                    "/login.html"
                )

            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        token = create_token(row[0], email, row[2])

        if is_form_post():
            return login_redirect(token)

        return json_with_cookie({
            "success": True,
            "message": "Login successful",
            "token": token,
            "role": row[2]
        }, 200, token)

    except Error as e:
        print("Login Error:", e)

        return jsonify({
            "success": False,
            "message": "Login failed"
        }), 500

    finally:
        if cursor:
            cursor.close()
        conn.close()


# ==========================================
# CURRENT USER
# ==========================================

@app.route("/api/me", methods=["GET"])
def me():

    payload = verify_token()

    if not payload:
        return jsonify({
            "success": False,
            "message": "Not logged in"
        }), 401

    return jsonify({
        "success": True,
        "email": payload["email"],
        "role": payload["role"]
    })


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout", methods=["GET", "POST"])
def logout():

    if request.method == "POST":
        response = jsonify({
            "success": True,
            "message": "Logged out"
        })
    else:
        response = redirect("/login.html")

    response.delete_cookie("token")
    return response


# ==========================================
# CREATE CIVIC COMPLAINT
# ==========================================

@app.route("/api/reports", methods=["POST"])
def create_report():

    payload = verify_token()

    if not payload:
        return jsonify({
            "success": False,
            "message": "Authentication required"
        }), 401

    data = get_input()

    description = (
        data.get("issue")
        or data.get("description")
        or data.get("Issue")
    )

    if not isinstance(description, str) or not description.strip():
        return jsonify({
            "success": False,
            "message": "Issue description is required"
        }), 400

    description = description.strip()
    analysis = ai_analyze_issue(description)

    conn = get_db()

    if not conn:
        return jsonify({
            "success": False,
            "message": "Database connection failed"
        }), 500

    cursor = None

    try:
        cursor = conn.cursor()

        complaint_id = (
            "CIV-" +
            datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        )

        query = """
            INSERT INTO civic_complaints (
                Complaint_ID, City, Area_Locality, Zone,
                Latitude, Longitude, Issue, Category,
                Responsible_Authority, Severity, AI_Confidence,
                Citizen_Support_Count, NGO_Involved,
                Citizen_Group_Active, Complaint_Status,
                Days_Open, AI_Auto_Routed, Evidence,
                Resolution_Verified, Priority_Score, User_ID
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
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
            0,
            "No",
            "No",
            "Pending",
            0,
            "Yes",
            data.get("evidence", "None"),
            "No",
            analysis["priority_score"],
            payload["user_id"]
        )

        cursor.execute(query, values)
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Report submitted successfully",
            "complaint_id": complaint_id,
            "analysis": analysis
        }), 201

    except Error as e:
        conn.rollback()
        print("Report Submission Error:", e)

        return jsonify({
            "success": False,
            "message": "Unable to submit report"
        }), 500

    finally:
        if cursor:
            cursor.close()
        conn.close()


# ==========================================
# LIST USER COMPLAINTS
# ==========================================

@app.route("/api/reports", methods=["GET"])
def list_reports():

    payload = verify_token()

    if not payload:
        return jsonify({
            "success": False,
            "message": "Authentication required"
        }), 401

    conn = get_db()

    if not conn:
        return jsonify({
            "success": False,
            "message": "Database connection failed"
        }), 500

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        columns = """
            Complaint_ID, City, Area_Locality, Issue, Category,
            Responsible_Authority, Severity, Complaint_Status,
            Days_Open, Resolution_Verified, Priority_Score, Created_At
        """

        if payload.get("role") == "admin":
            cursor.execute(
                f"SELECT {columns} FROM civic_complaints "
                "ORDER BY Created_At DESC"
            )
        else:
            cursor.execute(
                f"SELECT {columns} FROM civic_complaints "
                "WHERE User_ID = %s ORDER BY Created_At DESC",
                (payload["user_id"],)
            )

        return jsonify({
            "success": True,
            "reports": cursor.fetchall()
        })

    except Error as e:
        print("List Reports Error:", e)

        return jsonify({
            "success": False,
            "message": "Unable to fetch reports"
        }), 500

    finally:
        if cursor:
            cursor.close()
        conn.close()


# ==========================================
# TRACK COMPLAINT
# ==========================================

@app.route("/api/reports/<complaint_id>", methods=["GET"])
def track_report(complaint_id):

    payload = verify_token()

    if not payload:
        return jsonify({
            "success": False,
            "message": "Authentication required"
        }), 401

    conn = get_db()

    if not conn:
        return jsonify({
            "success": False,
            "message": "Database connection failed"
        }), 500

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT Complaint_ID, City, Area_Locality, Issue,
                   Category, Responsible_Authority, Severity,
                   Complaint_Status, Days_Open, Resolution_Verified,
                   Priority_Score, User_ID
            FROM civic_complaints
            WHERE Complaint_ID = %s
        """, (complaint_id,))

        row = cursor.fetchone()

        if not row:
            return jsonify({
                "success": False,
                "message": "Report not found"
            }), 404

        if (
            payload.get("role") != "admin"
            and row["User_ID"] != payload["user_id"]
        ):
            return jsonify({
                "success": False,
                "message": "Report not found"
            }), 404

        row.pop("User_ID", None)

        return jsonify({
            "success": True,
            "report": row
        })

    except Error as e:
        print("Track Report Error:", e)

        return jsonify({
            "success": False,
            "message": "Unable to fetch report"
        }), 500

    finally:
        if cursor:
            cursor.close()
        conn.close()


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "success": True,
        "message": "ApnaCity Civic API is running"
    })


# ==========================================
# SERVE WEBSITE FILES
# ==========================================

ALLOWED_EXT = (
    ".html", ".jpg", ".jpeg", ".png", ".gif",
    ".svg", ".webp", ".css", ".js", ".ico"
)


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

    if not filename.lower().endswith(ALLOWED_EXT):
        return jsonify({
            "success": False,
            "message": "Not found"
        }), 404

    return send_from_directory(BASE_DIR, filename)


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    if SECRET_KEY == "CHANGE_THIS_SECRET":
        print("WARNING: Change your JWT_SECRET in .env")

    if not init_db():
        print(
            "Database unavailable. Check MySQL service "
            "and your .env credentials."
        )

    URL = "http://127.0.0.1:5000/"

    print("Opening ApnaCity:", URL)

    threading.Timer(
        1.2,
        lambda: webbrowser.open(URL)
    ).start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=DEBUG,
        use_reloader=False
    )
