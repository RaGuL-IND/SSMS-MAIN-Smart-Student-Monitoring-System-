"""
Consolidated Flask application — Single Server Entry Point
Runs on Port 5000 (configurable via .env). All portals accessible via URL prefixes:
  /admin   → Admin Portal
  /student → Student Portal
  /company → Company Portal
  /api     → JSON API for the new React frontend (NEW)
"""

import os
from flask import Flask, render_template, send_from_directory
from dotenv import load_dotenv
from flask_cors import CORS                      # NEW — pip install flask-cors
from models import db  # SQLAlchemy instance
from blueprints.api_admin import api_admin_bp
from blueprints.api_students import api_students_bp
from blueprints.api_certificates import api_certificates_bp
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FRONTEND_DIST = os.path.join(BASE_DIR, "Frontend", "dist")
# Load environment variables from .env file
load_dotenv()


DATA_DIR  = os.path.join(BASE_DIR, "data")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

# -----------------------------------------------
# CORS — allows the React dev server (e.g. localhost:5173) to call
# /api/* with cookies attached. Only affects /api/* routes; your
# existing server-rendered pages are unaffected.               # NEW
# -----------------------------------------------
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
CORS(app, resources={r"/api/*": {"origins": FRONTEND_ORIGIN}}, supports_credentials=True)

# Needed so the session cookie set by /api/auth/login is sent back by the
# browser on subsequent cross-origin fetch() calls from the React dev
# server. In production, once React is served from the same domain as
# Flask (or behind the same reverse proxy), you can drop SAMESITE="None"
# and this whole block reduces to the two SESSION_COOKIE_* lines removed.  # NEW
if app.debug or os.environ.get("FLASK_DEBUG", "True").lower() == "true":
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False
else:
    app.config["SESSION_COOKIE_SAMESITE"] = "None"
    app.config["SESSION_COOKIE_SECURE"] = True
# -----------------------------------------------
# SQLAlchemy — SQLite database configuration
# -----------------------------------------------
DB_PATH = os.path.join(DATA_DIR, "portal.db")
app.config["SQLALCHEMY_DATABASE_URI"]        = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"]      = {"connect_args": {"check_same_thread": False}}

db.init_app(app)

# Secret key loaded from .env — never hardcoded
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret_change_this_in_production")

app.register_blueprint(api_admin_bp, url_prefix="/api/admin")
app.register_blueprint(api_students_bp, url_prefix="/api/admin/students")
app.register_blueprint(api_certificates_bp, url_prefix="/api/admin/certificates")
# -----------------------------------------------
# Register Blueprints with URL prefixes
# -----------------------------------------------

from blueprints.admin    import admin_bp
from blueprints.student  import student_bp
from blueprints.company  import company_bp
from blueprints.api_auth import api_auth_bp       # NEW

app.register_blueprint(admin_bp,   url_prefix="/admin")
app.register_blueprint(student_bp, url_prefix="/student")
app.register_blueprint(company_bp, url_prefix="/company")
app.register_blueprint(api_auth_bp, url_prefix="/api/auth")   # NEW


# -----------------------------------------------
# React Frontend
# -----------------------------------------------

# Serve Vite build assets
@app.route("/assets/<path:filename>")
def frontend_assets(filename):
    return send_from_directory(
        os.path.join(FRONTEND_DIST, "assets"),
        filename
    )


# Serve React application
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def frontend(path):
    """
    Serve the React application for every frontend route.
    Flask blueprints (/admin, /student, /company, /api)
    continue to work normally because they are matched
    before this catch-all route.
    """

    # If someone requests a real file inside dist/
    file_path = os.path.join(FRONTEND_DIST, path)
    if path and os.path.exists(file_path):
        return send_from_directory(FRONTEND_DIST, path)

    # Otherwise always return React
    return send_from_directory(FRONTEND_DIST, "index.html")

# -----------------------------------------------
# DB Init + one-time CSV migration on startup
# -----------------------------------------------
with app.app_context():
    db.create_all()                        # create tables if they don't exist
    _sentinel = os.path.join(DATA_DIR, ".db_migrated")
    if not os.path.exists(_sentinel):
        try:
            from db_init import run_migration
            print("\n🔄 First run — migrating CSV data to SQLite...\n")
            run_migration(app, db)
            open(_sentinel, "w").write("done")    # mark migration as done
        except Exception as _e:
            print(f"⚠️  Migration warning: {_e}")


if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    print("\n" + "="*60)
    print("  Internship Portal — Consolidated Server")
    print("="*60)
    print(f"  Admin  Portal : http://localhost:{port}/admin")
    print(f"  Student Portal: http://localhost:{port}/student")
    print(f"  Company Portal: http://localhost:{port}/company")
    print(f"  React API     : http://localhost:{port}/api/auth")
    print("="*60 + "\n")
    app.run(debug=debug, port=port)
