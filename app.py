"""
Consolidated Flask application — Single Server Entry Point
Runs on Port 5000 (configurable via .env). All portals accessible via URL prefixes:
  /admin   → Admin Portal
  /student → Student Portal
  /company → Company Portal
  /api     → JSON API for the React frontend
  /        → React app (built), served as static files
"""

import os
from flask import Flask, render_template, send_from_directory
from dotenv import load_dotenv
from flask_cors import CORS
from models import db  # SQLAlchemy instance

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")

# Where `npm run build` outputs the compiled React app.
# ⚠️ adjust to match your actual frontend folder name/path
REACT_DIST_DIR = os.path.join(BASE_DIR, "Frontend", "dist")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

# -----------------------------------------------
# CORS — only matters if you're still running the Vite dev server
# separately (see run_dev.py). Once Flask serves the built React app
# directly, everything is same-origin and this has no effect on those
# requests — harmless to leave in for local dev.
# -----------------------------------------------
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
CORS(app, resources={r"/api/*": {"origins": FRONTEND_ORIGIN}}, supports_credentials=True)

if app.debug or os.environ.get("FLASK_DEBUG", "True").lower() == "true":
    app.config["SESSION_COOKIE_SAMESITE"] = "None"
    app.config["SESSION_COOKIE_SECURE"] = False

# -----------------------------------------------
# SQLAlchemy — SQLite database configuration
# -----------------------------------------------
DB_PATH = os.path.join(DATA_DIR, "portal.db")
app.config["SQLALCHEMY_DATABASE_URI"]        = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"]      = {"connect_args": {"check_same_thread": False}}

db.init_app(app)

app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret_change_this_in_production")

# -----------------------------------------------
# Register Blueprints with URL prefixes
# -----------------------------------------------
from blueprints.admin    import admin_bp
from blueprints.student  import student_bp
from blueprints.company  import company_bp
from blueprints.api_auth import api_auth_bp

app.register_blueprint(admin_bp,   url_prefix="/admin")
app.register_blueprint(student_bp, url_prefix="/student")
app.register_blueprint(company_bp, url_prefix="/company")
app.register_blueprint(api_auth_bp, url_prefix="/api/auth")


# -----------------------------------------------
# React app — served at root
# -----------------------------------------------
# Run `npm run build` inside Frontend/ first (produces Frontend/dist/).
# Vite's default build emits root-absolute asset paths
# (<script src="/assets/....js">), which is why the assets route below
# lives at "/assets/..." rather than nested under any prefix — it must
# match exactly what the built index.html actually requests.
#
# If Frontend/dist doesn't exist yet (fresh clone, haven't built), this
# falls back to your old main_portal.html so the app doesn't 500.
#
# ⚠️ Once Frontend/dist/index.html exists, main_portal.html becomes
# unreachable at "/" — that's intentional (React replaces it) but flag
# it if that's not what you want yet.
@app.route("/")
@app.route("/login")
def home():
    index_path = os.path.join(REACT_DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(REACT_DIST_DIR, "index.html")
    return render_template("main_portal.html")


@app.route("/assets/<path:filename>")
def serve_react_assets(filename):
    return send_from_directory(os.path.join(REACT_DIST_DIR, "assets"), filename)


# -----------------------------------------------
# DB Init + one-time CSV migration on startup
# -----------------------------------------------
with app.app_context():
    db.create_all()
    _sentinel = os.path.join(DATA_DIR, ".db_migrated")
    if not os.path.exists(_sentinel):
        try:
            from db_init import run_migration
            print("\n🔄 First run — migrating CSV data to SQLite...\n")
            run_migration(app, db)
            open(_sentinel, "w").write("done")
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
    print(f"  React (built) : http://localhost:{port}/")
    print("="*60 + "\n")
    app.run(debug=debug, port=port)