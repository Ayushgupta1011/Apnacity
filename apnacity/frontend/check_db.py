"""check_db.py - find out why the database connection fails.

Run from your project folder:   python check_db.py
It reads the same .env file as civic.py and tells you what is wrong.
"""
import os

import mysql.connector
from mysql.connector import Error

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    print("Tip: pip install python-dotenv  (so .env can be read)")

host = os.getenv("DB_HOST", "localhost")
port = int(os.getenv("DB_PORT", "3306"))
user = os.getenv("DB_USER", "root")
password = os.getenv("DB_PASSWORD", "")
name = os.getenv("DB_NAME", "apnacity")
ssl_ca = os.getenv("DB_SSL_CA")

print("Settings being used")
print(f"  DB_HOST={host}  DB_PORT={port}  DB_USER={user}")
print(f"  DB_PASSWORD={'(empty)' if not password else '(set, ' + str(len(password)) + ' characters)'}")
print(f"  DB_NAME={name}\n")

HINTS = {
    2003: "Cannot reach the MySQL server. Is MySQL running? Check DB_HOST and DB_PORT "
          "(local: start MySQL; hosted: use the host name your database provider gave you, not 'localhost').",
    2002: "Cannot reach the MySQL server. Start MySQL, or check DB_HOST.",
    2005: "DB_HOST is not a valid host name. Copy it exactly from your database provider.",
    1045: "Wrong username or password. Check DB_USER and DB_PASSWORD in .env "
          "(no quotes, no spaces around the = sign).",
    1130: "This computer is not allowed to connect. On a hosted database, allow your IP / 'all hosts'.",
    1049: "The database does not exist yet. Create it:  CREATE DATABASE apnacity;  "
          "(or fix DB_NAME). civic.py can create it automatically only if the user has permission.",
    1044: "This user has no permission on that database. Grant it:  "
          "GRANT ALL ON apnacity.* TO 'user'@'%';",
    2026: "SSL problem. Cloud databases often need DB_SSL_CA=/path/to/ca.pem in .env.",
    2059: "Authentication method not supported. Update mysql-connector-python "
          "(pip install -U mysql-connector-python).",
}


def explain(e):
    print(f"  FAILED: {e}")
    hint = HINTS.get(getattr(e, "errno", None))
    if hint:
        print(f"  -> {hint}")


cfg = {"host": host, "port": port, "user": user, "password": password}
if ssl_ca:
    cfg["ssl_ca"] = ssl_ca

# Step 1: can we log in to the server at all?
print("Step 1: connect to the MySQL server")
try:
    conn = mysql.connector.connect(**cfg, connection_timeout=8)
    print(f"  OK (server version {conn.get_server_info()})")
except Error as e:
    explain(e)
    raise SystemExit("\nFix step 1 first, then run this again.")

# Step 2: does the database exist?
print(f"Step 2: look for database '{name}'")
cur = conn.cursor()
cur.execute("SHOW DATABASES LIKE %s", (name,))
if cur.fetchone():
    print("  OK, database exists")
else:
    print("  Database not found. Trying to create it...")
    try:
        cur.execute(f"CREATE DATABASE `{name}`")
        print("  OK, created")
    except Error as e:
        explain(e)
        conn.close()
        raise SystemExit("\nCreate the database yourself, then run this again.")
cur.close()
conn.close()

# Step 3: connect to the database itself and list tables
print(f"Step 3: connect to '{name}'")
try:
    conn = mysql.connector.connect(**cfg, database=name, connection_timeout=8)
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = [r[0] for r in cur.fetchall()]
    print("  OK, tables:", ", ".join(tables) if tables else "(none yet - start civic.py to create them)")
    cur.close()
    conn.close()
except Error as e:
    explain(e)
    raise SystemExit("\nFix step 3, then run this again.")

print("\nAll good. If the website still says 'Database connection failed',")
print("restart civic.py and read the line starting with 'Database Connection Error' in its window.")