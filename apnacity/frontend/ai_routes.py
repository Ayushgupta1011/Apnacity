"""ai_routes.py - AI endpoints for ApnaCity.

Adds:
  POST /api/generate-complaint   (login required) -> formal complaint letter
  POST /api/analyze              (login required) -> photo analysis
"""
import time
from collections import defaultdict, deque

from flask import jsonify, request

from ai import analyze_image, generate_complaint_letter

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}

# Simple per-user limit so nobody drains your Gemini quota (resets on restart)
LIMIT_PER_HOUR = 15
_calls = defaultdict(deque)


def _rate_limited(user_id):
    now = time.time()
    q = _calls[user_id]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= LIMIT_PER_HOUR:
        return True
    q.append(now)
    return False


def register_ai_routes(app, verify_token, get_db, detect_category, departments):

    @app.route("/api/generate-complaint", methods=["POST"])
    def generate_complaint():
        payload = verify_token()
        if not payload:
            return jsonify({"success": False, "message": "Authentication required"}), 401

        if _rate_limited(payload["user_id"]):
            return jsonify({"success": False,
                            "message": "Too many requests. Try again later."}), 429

        data = request.get_json(silent=True) or {}
        issue = (data.get("issue") or "").strip()
        if len(issue) < 10:
            return jsonify({"success": False,
                            "message": "Please describe the issue in a little more detail."}), 400

        # Pull the citizen's saved profile (name/address) from the database
        profile = {}
        conn = get_db()
        if conn:
            cursor = None
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT full_name, street, postal_code, city FROM users WHERE id = %s",
                    (payload["user_id"],),
                )
                profile = cursor.fetchone() or {}
            except Exception as e:
                print("Profile lookup error:", e)
            finally:
                if cursor:
                    cursor.close()
                conn.close()

        category = detect_category(issue)
        city = (data.get("city") or profile.get("city") or "").strip()
        address = ", ".join(
            p for p in [profile.get("street"), city, profile.get("postal_code")] if p
        )

        info = {
            "name": profile.get("full_name") or "",
            "address": address,
            "email": payload["email"],
            "city": city,
            "area": data.get("area"),
            "issue": issue,
            "category": category,
            "authority": departments.get(category, ""),
            "lat": data.get("latitude"),
            "lng": data.get("longitude"),
            "complaint_id": data.get("complaint_id"),
            "has_photo": bool(data.get("has_photo")),
            "language": data.get("language", "English"),
        }

        try:
            result = generate_complaint_letter(info)
        except Exception as e:
            print("Gemini letter error:", e)
            return jsonify({"success": False,
                            "message": "AI service is unavailable right now. Please try again."}), 502

        return jsonify({"success": True, **result})

    @app.route("/api/analyze", methods=["POST"])
    def analyze():
        payload = verify_token()
        if not payload:
            return jsonify({"error": "Authentication required"}), 401

        if _rate_limited(payload["user_id"]):
            return jsonify({"error": "Too many requests. Try again later."}), 429

        file = request.files.get("image")
        if not file:
            return jsonify({"error": "No image uploaded"}), 400

        mime = (file.mimetype or "").lower()
        if mime not in ALLOWED_MIME:
            return jsonify({"error": "Only JPG, PNG or WEBP images are allowed"}), 400

        image_bytes = file.read(MAX_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_IMAGE_BYTES:
            return jsonify({"error": "Image is larger than 5 MB"}), 413

        try:
            return jsonify(analyze_image(image_bytes, mime))
        except Exception as e:
            print("Gemini image error:", e)
            return jsonify({"error": "AI service is unavailable right now."}), 502