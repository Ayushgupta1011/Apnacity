# ApnaCity Project Documentation

## Overview

ApnaCity is a civic issue-reporting platform built with Flask, MySQL, HTML, CSS, and JavaScript. Citizens can register complaints, add locations and photos, generate formal letters, track status, support other complaints, and view verified resolutions. Administrators can review reports and update resolution status.

## Technology Stack

- **Backend:** Python and Flask
- **Database:** MySQL or a MySQL-compatible hosted database
- **Authentication:** JWT in an HTTP-only cookie
- **Frontend:** HTML, CSS, and vanilla JavaScript
- **AI:** Google Gemini
- **Media storage:** Local server storage
- **Optional notifications:** Twilio SMS

## Project Structure

```text
apnacity/
├── DSocumentation.md
├── requirements.txt
├── .vscode/
│   └── launch.json
├── .cursor/
│   └── rules/doc-maker.mdc
└── frontend/
    ├── civic.py              # Main Flask app and core routes
    ├── ai.py                 # Gemini letter/photo helpers
    ├── ai_routes.py          # AI API routes
    ├── extras.py             # Photos, support, and public impact
    ├── notify.py             # Notifications and optional SMS
    ├── storage.py            # Complaint photo folder helper
    ├── dashboard.py          # Reserved dashboard implementation
    ├── auth.js               # Authentication and page protection
    ├── report.js             # Report submission and AI interaction
    ├── community.js
    ├── other.js
    ├── index.html
    ├── login.html
    ├── signin.html
    ├── Register_a_Issue.html
    ├── Track_report_status.html
    ├── verified_impact.html
    ├── admin_dashboard.html
    ├── Ngo.html
    ├── comunity.html
    ├── community.css
    ├── img/
    └── requirements.txt
```

## Local Setup

### 1. Install dependencies

```powershell
cd C:\Users\AYUSH\Desktop\apnacity\frontend
pip install -r requirements.txt
```

### 2. Configure MySQL

Start MySQL and provide valid database credentials. The application creates the database and required tables automatically when a local database is available.

### 3. Create `frontend/.env`

```dotenv
JWT_SECRET=replace-this-with-a-long-random-secret
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-password
DB_NAME=apnacity

COOKIE_SECURE=false
FLASK_DEBUG=false
ALLOW_ADMIN_SIGNUP=false
IMPACT_ADMIN_ONLY=false
AUTO_INIT=true
UPLOAD_ROOT=C:\Users\AYUSH\Desktop\apnacity\frontend

GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=

SMS_ENABLED=false
TWILIO_SID=
TWILIO_TOKEN=
TWILIO_FROM=
```

`DB_SSL_CA` can be set to an SSL certificate path for hosted MySQL providers.

### 4. Run the project

```powershell
python civic.py
```

Open `http://127.0.0.1:5000/`.

Useful diagnostics:

```powershell
python check_db.py
python check_ai.py
```

## Configuration Reference

| Variable | Default | Purpose |
|---|---|---|
| `JWT_SECRET` | Development fallback | Signs authentication tokens |
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | MySQL username |
| `DB_PASSWORD` | Empty | MySQL password |
| `DB_NAME` | `apnacity` | Database name |
| `DB_SSL_CA` | None | Optional MySQL SSL CA |
| `COOKIE_SECURE` | `false` | Makes authentication cookies HTTPS-only |
| `FLASK_DEBUG` | `false` | Enables Flask debug mode |
| `ALLOW_ADMIN_SIGNUP` | `false` | Allows signup requests to create admins |
| `IMPACT_ADMIN_ONLY` | `false` | Restricts impact-photo uploads to admins |
| `UPLOAD_ROOT` | `frontend/` | Persistent upload directory |
| `AUTO_INIT` | `true` | Initializes database and modules at import |
| `GEMINI_API_KEY` | None | Enables Gemini features |
| `GEMINI_MODEL` | None | Forces a Gemini model |
| `SMS_ENABLED` | `false` | Enables Twilio SMS |
| `TWILIO_SID` | None | Twilio account SID |
| `TWILIO_TOKEN` | None | Twilio token |
| `TWILIO_FROM` | None | Twilio sender number |

Always replace the development JWT secret in deployed environments.

## Database Schema

### `users`

Stores account identity and profile details:

- `id`
- `email`
- `password_hash`
- `role`
- `full_name`
- `street`
- `postal_code`
- `city`
- `created_at`

### `civic_complaints`

Stores complaint location, description, category, authority, severity, status, evidence, priority, ownership, and optional complaint letter and contact phone.

### Supporting Tables

- `impact_images`: Featured before/after images
- `complaint_supports`: One support vote per user and complaint
- `notifications`: Complaint status updates

Database startup functions create missing tables, columns, and indexes automatically.

## Application Flow

1. A citizen registers or signs in.
2. JWT authentication protects complaint operations.
3. The report page collects issue details, location, and an optional photo.
4. Gemini can analyze the photo and generate a formal letter.
5. Flask detects similar open complaints near the submitted coordinates.
6. The complaint is stored and receives an ID such as `APNA-20261127-7D82B8`.
7. Citizens track status and notifications.
8. Admins update status and mark resolved complaints as verified.
9. Verified cases appear in the public impact pages.

## Frontend Pages

| Page | Purpose |
|---|---|
| `index.html` | Public landing page |
| `login.html` | Login |
| `signin.html` | Registration |
| `Register_a_Issue.html` | Protected complaint submission |
| `Track_report_status.html` | Status and notification tracking |
| `verified_impact.html` | Public verified resolutions |
| `admin_dashboard.html` | Administrative interface |
| `Ngo.html` | NGO information |
| `comunity.html` | Community activities |

## Core API Endpoints

### Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/signup` | Create an account |
| POST | `/login` | Authenticate a user |
| POST or GET | `/logout` | End a session |
| GET | `/api/me` | Get the current user |
| GET | `/api/health` | Health check |

### Complaints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/reports` | Submit a complaint |
| GET | `/api/reports` | List user reports or all reports for an admin |
| GET | `/api/reports/<id>` | Get one complaint |
| POST | `/api/reports/<id>/photo` | Upload before or after evidence |
| POST | `/api/reports/<id>/support` | Add one support vote |

### AI

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/analyze` | Analyze an uploaded civic issue photo |
| POST | `/api/generate-complaint` | Generate a formal complaint letter |

AI operations are limited to 15 calls per user per hour. This limit resets when the server restarts.

### Notifications and Status

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/notifications` | Retrieve updates |
| POST | `/api/notifications/read` | Mark updates as read |
| POST | `/api/admin/reports/<id>/status` | Update status and notify the citizen |

### Impact and Media

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/impact` | Public impact statistics |
| GET | `/api/impact/<id>` | Public or authorized complaint impact lookup |
| GET | `/api/impact-photos` | Featured before/after photos |
| POST | `/api/impact-photos/upload` | Upload featured photos |
| GET | `/media/<filename>` | Serve protected complaint evidence |
| GET | `/uploads/<filename>` | Serve public impact uploads |

## AI Behavior

`ai.py` tries preferred Gemini models until one works and remembers the successful model for the running process.

When Gemini is unavailable or not configured:

- Image analysis reports that AI is unavailable.
- Complaint generation uses a standard fallback letter.
- Core complaint submission remains usable.

## Security and Access

- Upload limit: 5 MB.
- Real image signatures are checked for supported image types.
- JWTs are accepted from HTTP-only cookies or bearer headers.
- Citizens can access only their own complaints.
- Admin-only operations require the `admin` role.
- Complaint photos are not exposed through generic static-file routes.
- Resolved and verified evidence becomes public only after verification.

## Deployment

For Render or another hosted platform:

1. Install dependencies from `requirements.txt`.
2. Set the start command to `gunicorn civic:app` from `frontend/`.
3. Configure MySQL environment variables.
4. Set a strong `JWT_SECRET`.
5. Set `COOKIE_SECURE=true` for HTTPS.
6. Set `UPLOAD_ROOT` to persistent storage.

Ephemeral hosting disks may delete uploaded files after restart or deployment. Use persistent disk storage or cloud object storage for production media.

## Creating an Admin

For safer normal operation, create a normal account and update the database:

```sql
UPDATE users
SET role = 'admin'
WHERE email = 'admin@example.com';
```

Admin signup can also be enabled with `ALLOW_ADMIN_SIGNUP=true`.
