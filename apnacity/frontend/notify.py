"""notify.py - complaint IDs, dashboard updates (notifications) and optional SMS.

Adds:
  GET  /api/notifications?complaint_id=...      the logged-in user's updates
  POST /api/notifications/read                  mark them as read
  POST /api/admin/reports/<id>/status           admin changes status -> notifies the citizen

SMS is OFF unless SMS_ENABLED=true and the Twilio settings are in .env.
Without SMS, everything still works through the dashboard (Track Status page).
"""
import datetime
import os
import re
import secrets
import threading

import requests
from flask import jsonify, request

STATUSES = ("Pending", "In Progress", "Resolved", "Rejected")

_get_db = None


# ------------------------------------------------------------------
# IDs and phone numbers
# ------------------------------------------------------------------
def new_complaint_id():
    """Example: APNA-20261126-9F3A1C"""
    return ("APNA-" + datetime.date.today().strftime("%Y%m%d")
            + "-" + secrets.token_hex(3).upper())


def normalize_phone(raw):
    """Indian mobile numbers only. Returns +91XXXXXXXXXX or None."""
    s = re.sub(r"[\s\-()]", "", str(raw or ""))
    if re.fullmatch(r"[6-9]\d{9}", s):
        return "+91" + s
    if re.fullmatch(r"91[6-9]\d{9}", s):
        return "+" + s
    if re.fullmatch(r"\+91[6-9]\d{9}", s):
        return s
    return None


# ------------------------------------------------------------------
# SMS (Twilio REST API; replace the body of _send_sms for MSG91 etc.)
# ------------------------------------------------------------------
def _send_sms(phone, text):
    if os.getenv("SMS_ENABLED", "false").lower() != "true":
        print("[SMS disabled] would send to", phone)
        return
    sid = os.getenv("TWILIO_SID")
    token = os.getenv("TWILIO_TOKEN")
    sender = os.getenv("TWILIO_FROM")
    if not (sid and token and sender):
        print("SMS settings missing in environment")
        return
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"To": phone, "From": sender, "Body": text[:300]},
            auth=(sid, token),
            timeout=10,
        )
        if r.status_code >= 300:
            print("SMS failed:", r.status_code, r.text[:200])
    except requests.RequestException as e:
        print("SMS error:", e)


def send_sms_async(phone, text):
    if phone:
        threading.Thread(target=_send_sms, args=(phone, text), daemon=True).start()


# ------------------------------------------------------------------
# Database
# ------------------------------------------------------------------
def ensure_schema():
    conn = _get_db()
    if not conn:
        return
    cur = None
    try:
        cur = conn.cursor()
        for col, ddl in (("Complaint_Letter", "TEXT NULL"),
                         ("Contact_Phone", "VARCHAR(20) NULL")):
            cur.execute("SHOW COLUMNS FROM civic_complaints LIKE %s", (col,))
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE civic_complaints ADD COLUMN {col} {ddl}")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                complaint_id VARCHAR(40) NOT NULL,
                message VARCHAR(500) NOT NULL,
                is_read TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user (user_id, is_read),
                INDEX idx_complaint (complaint_id)
            )
        """)
        conn.commit()
    except Exception as e:
        print("notify.ensure_schema error:", e)
    finally:
        if cur:
            cur.close()
        conn.close()


def notify_user(user_id, complaint_id, message, phone=None):
    """Save a dashboard update and (optionally) send an SMS."""
    if user_id is None:
        return
    conn = _get_db()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO notifications (user_id, complaint_id, message) VALUES (%s, %s, %s)",
                (user_id, complaint_id, message[:500]),
            )
            conn.commit()
        except Exception as e:
            print("notify_user error:", e)
        finally:
            if cur:
                cur.close()
            conn.close()
    send_sms_async(phone, "ApnaCity: " + message)


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
def register_notify_routes(app, verify_token, get_db):
    global _get_db
    _get_db = get_db
    ensure_schema()  # call this AFTER init_db() so civic_complaints exists

    @app.route("/api/notifications", methods=["GET"])
    def list_notifications():
        payload = verify_token()
        if not payload:
            return jsonify({"success": False, "message": "Authentication required"}), 401

        complaint_id = (request.args.get("complaint_id") or "").strip()
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        cur = None
        try:
            cur = conn.cursor(dictionary=True)
            sql = ("SELECT id, complaint_id, message, is_read, created_at "
                   "FROM notifications WHERE user_id = %s")
            args = [payload["user_id"]]
            if complaint_id:
                sql += " AND complaint_id = %s"
                args.append(complaint_id)
            sql += " ORDER BY created_at DESC, id DESC LIMIT 50"
            cur.execute(sql, args)
            rows = cur.fetchall()
            return jsonify({
                "success": True,
                "unread": sum(1 for r in rows if not r["is_read"]),
                "notifications": rows,
            })
        except Exception as e:
            print("List notifications error:", e)
            return jsonify({"success": False, "message": "Unable to fetch updates"}), 500
        finally:
            if cur:
                cur.close()
            conn.close()

    @app.route("/api/notifications/read", methods=["POST"])
    def read_notifications():
        payload = verify_token()
        if not payload:
            return jsonify({"success": False, "message": "Authentication required"}), 401

        data = request.get_json(silent=True) or {}
        complaint_id = (data.get("complaint_id") or "").strip()
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        cur = None
        try:
            cur = conn.cursor()
            sql = "UPDATE notifications SET is_read = 1 WHERE user_id = %s"
            args = [payload["user_id"]]
            if complaint_id:
                sql += " AND complaint_id = %s"
                args.append(complaint_id)
            cur.execute(sql, args)
            conn.commit()
            return jsonify({"success": True})
        except Exception as e:
            print("Read notifications error:", e)
            return jsonify({"success": False, "message": "Unable to update"}), 500
        finally:
            if cur:
                cur.close()
            conn.close()

    @app.route("/api/admin/reports/<complaint_id>/status", methods=["POST"])
    def admin_update_status(complaint_id):
        payload = verify_token()
        if not payload:
            return jsonify({"success": False, "message": "Authentication required"}), 401
        if payload.get("role") != "admin":
            return jsonify({"success": False, "message": "Admin access required"}), 403

        data = request.get_json(silent=True) or {}
        status = (data.get("status") or "").strip()
        note = (data.get("note") or "").strip()[:200]
        if status not in STATUSES:
            return jsonify({"success": False, "message": "Invalid status"}), 400

        conn = get_db()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        cur = None
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT User_ID, Contact_Phone FROM civic_complaints WHERE Complaint_ID = %s",
                (complaint_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"success": False, "message": "Report not found"}), 404

            cur.execute(
                "UPDATE civic_complaints SET Complaint_Status = %s, Resolution_Verified = %s "
                "WHERE Complaint_ID = %s",
                (status, "Yes" if status == "Resolved" else "No", complaint_id),
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("Status update error:", e)
            return jsonify({"success": False, "message": "Unable to update status"}), 500
        finally:
            if cur:
                cur.close()
            conn.close()

        message = f"Update on {complaint_id}: status is now {status}."
        if note:
            message += f" Note: {note}"
        notify_user(row["User_ID"], complaint_id, message, row["Contact_Phone"])

        return jsonify({"success": True, "status": status})