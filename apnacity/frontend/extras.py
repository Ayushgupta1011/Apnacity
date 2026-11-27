"""extras.py - photos, community support, public impact data.

Adds:
  POST /api/reports/<id>/photo     upload "before" (owner/admin) or "after" (admin) photo
  GET  /media/<filename>           serve a photo (owner, admin, or public once verified)
  POST /api/reports/<id>/support   support an open complaint (one vote per user)
  GET  /api/impact                 public stats + verified-resolved complaints (no personal data)
"""
import os
import re

from flask import jsonify, request, send_from_directory

MAX_IMAGE_BYTES = 5 * 1024 * 1024
UPLOAD_FOLDER_NAME = "user_uploads"   # never served by the generic file route


def _image_type(head):
    """Check the real file type from its first bytes (not the browser's claim)."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def _ensure_schema(get_db):
    conn = get_db()

    if not conn:
        print("Schema Error: Database connection unavailable")
        return False

    cur = None

    try:
        # Buffered cursor plus explicitly consuming every result
        cur = conn.cursor(buffered=True)

        # Required columns in civic_complaints
        required_columns = {
            "After_Evidence": "VARCHAR(255) NULL",
            "Complaint_Letter": "TEXT NULL",
            "Contact_Phone": "VARCHAR(20) NULL"
        }

        for column_name, column_type in required_columns.items():

            cur.execute(
                "SHOW COLUMNS FROM civic_complaints LIKE %s",
                (column_name,)
            )

            rows = cur.fetchall()

            if not rows:
                cur.execute(
                    f"ALTER TABLE civic_complaints "
                    f"ADD COLUMN `{column_name}` {column_type}"
                )
                print(f"Added database column: {column_name}")

        # Community support table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS complaint_supports (
                complaint_id VARCHAR(40) NOT NULL,
                user_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (complaint_id, user_id)
            )
        """)

        # Required database indexes
        indexes = {
            "idx_status": "Complaint_Status",
            "idx_user": "User_ID",
            "idx_geo": "Category, Latitude, Longitude"
        }

        for index_name, columns in indexes.items():

            cur.execute(
                "SHOW INDEX FROM civic_complaints WHERE Key_name = %s",
                (index_name,)
            )

            rows = cur.fetchall()

            if not rows:
                cur.execute(
                    f"ALTER TABLE civic_complaints "
                    f"ADD INDEX `{index_name}` ({columns})"
                )
                print(f"Created database index: {index_name}")

        conn.commit()

        print("Extras database schema initialized successfully!")
        return True

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass

        print("Extras schema initialization error:", repr(e))
        return False

    finally:
        if cur:
            try:
                cur.close()
            except Exception as e:
                print("Cursor close warning:", e)

        try:
            conn.close()
        except Exception as e:
            print("Connection close warning:", e)



def register_extra_routes(app, verify_token, get_db, base_dir):
    upload_dir = os.path.join(base_dir, UPLOAD_FOLDER_NAME)
    os.makedirs(upload_dir, exist_ok=True)
    _ensure_schema(get_db)

    def fetch_complaint(cid):
        conn = get_db()
        if not conn:
            return None, "db"
        cur = None
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT Complaint_ID, User_ID, Complaint_Status, Resolution_Verified, "
                "Evidence, After_Evidence FROM civic_complaints WHERE Complaint_ID = %s",
                (cid,),
            )
            return cur.fetchone(), None
        finally:
            if cur:
                cur.close()
            conn.close()

    # ---------------- upload photo ----------------
    @app.route("/api/reports/<complaint_id>/photo", methods=["POST"])
    def upload_photo(complaint_id):
        payload = verify_token()
        if not payload:
            return jsonify({"success": False, "message": "Authentication required"}), 401

        kind = (request.form.get("kind") or "before").lower()
        if kind not in ("before", "after"):
            return jsonify({"success": False, "message": "Invalid photo type"}), 400

        is_admin = payload.get("role") == "admin"
        if kind == "after" and not is_admin:
            return jsonify({"success": False, "message": "Admin access required"}), 403

        row, err = fetch_complaint(complaint_id)
        if err:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        if not row or (not is_admin and row["User_ID"] != payload["user_id"]):
            return jsonify({"success": False, "message": "Report not found"}), 404

        file = request.files.get("image")
        if not file:
            return jsonify({"success": False, "message": "No image uploaded"}), 400
        data = file.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            return jsonify({"success": False, "message": "Image is larger than 5 MB"}), 413
        ext = _image_type(data[:16])
        if not ext:
            return jsonify({"success": False, "message": "Only JPG, PNG or WEBP images are allowed"}), 400

        safe_id = re.sub(r"[^A-Za-z0-9\-]", "", complaint_id)
        filename = f"{safe_id}_{kind}.{ext}"

        # remove an older photo of the same kind that had a different extension
        for old in ("jpg", "png", "webp"):
            old_path = os.path.join(upload_dir, f"{safe_id}_{kind}.{old}")
            if old != ext and os.path.exists(old_path):
                os.remove(old_path)
        with open(os.path.join(upload_dir, filename), "wb") as f:
            f.write(data)

        column = "Evidence" if kind == "before" else "After_Evidence"
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(f"UPDATE civic_complaints SET {column} = %s WHERE Complaint_ID = %s",
                        (filename, complaint_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("photo db error:", e)
            return jsonify({"success": False, "message": "Could not save photo"}), 500
        finally:
            if cur:
                cur.close()
            conn.close()

        return jsonify({"success": True, "filename": filename})

    # ---------------- serve photo ----------------
    @app.route("/media/<filename>", methods=["GET"])
    def media(filename):
        m = re.fullmatch(r"([A-Za-z0-9\-]+)_(before|after)\.(jpg|png|webp)", filename)
        if not m:
            return jsonify({"success": False, "message": "Not found"}), 404
        row, err = fetch_complaint(m.group(1))
        if err or not row:
            return jsonify({"success": False, "message": "Not found"}), 404

        public = row["Resolution_Verified"] == "Yes" and row["Complaint_Status"] == "Resolved"
        if not public:
            payload = verify_token()
            if not payload or (payload.get("role") != "admin"
                               and row["User_ID"] != payload.get("user_id")):
                return jsonify({"success": False, "message": "Not found"}), 404

        resp = send_from_directory(upload_dir, filename)
        resp.headers["Cache-Control"] = "private, max-age=300" if not public else "public, max-age=3600"
        return resp

    # ---------------- support a complaint ----------------
    @app.route("/api/reports/<complaint_id>/support", methods=["POST"])
    def support(complaint_id):
        payload = verify_token()
        if not payload:
            return jsonify({"success": False, "message": "Authentication required"}), 401

        row, err = fetch_complaint(complaint_id)
        if err:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        if not row:
            return jsonify({"success": False, "message": "Report not found"}), 404
        if row["User_ID"] == payload["user_id"]:
            return jsonify({"success": False, "message": "You cannot support your own complaint"}), 400

        conn = get_db()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT IGNORE INTO complaint_supports (complaint_id, user_id) VALUES (%s, %s)",
                (complaint_id, payload["user_id"]),
            )
            added = cur.rowcount == 1
            if added:
                cur.execute(
                    "UPDATE civic_complaints SET Citizen_Support_Count = Citizen_Support_Count + 1 "
                    "WHERE Complaint_ID = %s", (complaint_id,))
            cur.execute("SELECT Citizen_Support_Count FROM civic_complaints WHERE Complaint_ID = %s",
                        (complaint_id,))
            count = cur.fetchone()[0]
            conn.commit()
            return jsonify({"success": True, "added": added, "count": count,
                            "message": "Thanks for your support!" if added
                            else "You already supported this complaint"})
        except Exception as e:
            conn.rollback()
            print("support error:", e)
            return jsonify({"success": False, "message": "Could not save support"}), 500
        finally:
            if cur:
                cur.close()
            conn.close()

    # ---------------- public impact ----------------
    @app.route("/api/impact", methods=["GET"])
    def impact():
        conn = get_db()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed"}), 500
        cur = None
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT COUNT(*) AS total,
                       SUM(Complaint_Status = 'Resolved') AS resolved,
                       SUM(Resolution_Verified = 'Yes' AND Complaint_Status = 'Resolved') AS verified,
                       COUNT(DISTINCT City) AS cities
                FROM civic_complaints
            """)
            stats = cur.fetchone() or {}
            cur.execute("""
                SELECT Complaint_ID, Category, City, Area_Locality,
                       LEFT(Issue, 160) AS Issue, Citizen_Support_Count,
                       Evidence, After_Evidence, Created_At
                FROM civic_complaints
                WHERE Resolution_Verified = 'Yes' AND Complaint_Status = 'Resolved'
                ORDER BY Created_At DESC LIMIT 12
            """)
            items = cur.fetchall()
            for it in items:
                it["before_url"] = f"/media/{it['Evidence']}" if it["Evidence"] not in (None, "", "None") else None
                it["after_url"] = f"/media/{it['After_Evidence']}" if it["After_Evidence"] else None
                it.pop("Evidence", None)
                it.pop("After_Evidence", None)
            return jsonify({
                "success": True,
                "stats": {k: int(v or 0) for k, v in stats.items()},
                "items": items,
            })
        except Exception as e:
            print("impact error:", e)
            return jsonify({"success": False, "message": "Unable to load impact data"}), 500
        finally:
            if cur:
                cur.close()
            conn.close()
