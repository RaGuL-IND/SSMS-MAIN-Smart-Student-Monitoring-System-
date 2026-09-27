"""
blueprints/api_auth.py
-----------------------------------------------------------------------------
NEW, ADDITIVE blueprint for the React/TypeScript login page.

Why a separate blueprint instead of editing admin.py / student.py / company.py:
  Your existing HTML-form routes (admin.login, company.company_login, the
  student login route, etc.) keep working exactly as before — nothing about
  them changes. This blueprint just exposes the SAME login logic over JSON,
  under /api/auth/*, and writes to the SAME Flask `session` object your
  existing @login_required-style checks presumably read from.

⚠️ THINGS I HAD TO GUESS — please check these against your real code:
  1. `models.py` wasn't provided, so the Student / Company model field names
     below (register_number, password, email, password_hash, ...) are my
     best inference from utils.py and your Jinja templates. Adjust the
     query/field names to match your actual models.
  2. Session keys (`session["admin_username"]`, `session["student_reg"]`,
     `session["company_email"]`, `session["role"]`) are placeholders. Open
     your existing blueprints/admin.py, student.py, company.py and search
     for `session[` — copy the EXACT keys they set on successful login, and
     replace the ones below. If the keys don't match, your existing
     @login_required decorators won't recognize this new login as "logged in".
  3. Student passwords: utils.py's `_df_row_to_student_obj` stores
     `Password` as a plain field (no hashing helper is used on it anywhere
     in utils.py), so I compare it directly. If you hash student passwords
     elsewhere, swap in `check_password_hash` instead.
  4. Redirect URLs (/admin/dashboard, /student/dashboard, /company/dashboard)
     are guesses — point them at your real post-login routes.

Install:
    pip install flask-cors
"""

from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash

from utils import verify_admin  # already exists in your codebase

api_auth_bp = Blueprint("api_auth", __name__)

DEFAULT_STUDENT_PASSWORD = "helloeveryone"


@api_auth_bp.post("/login")
def api_login():
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").strip().lower()
    identifier = (data.get("identifier") or "").strip()
    password = data.get("password") or ""

    if not role or not identifier or not password:
        return jsonify(success=False, message="Missing credentials."), 400

    if role == "admin":
        return _login_admin(identifier, password)
    if role == "student":
        return _login_student(identifier, password)
    if role == "company":
        return _login_company(identifier, password)

    return jsonify(success=False, message="Unknown role."), 400


@api_auth_bp.post("/logout")
def api_logout():
    session.clear()
    return jsonify(success=True)


@api_auth_bp.get("/me")
def api_me():
    """Lets the React app check 'am I already logged in?' on page load."""
    role = session.get("role")
    if not role:
        return jsonify(authenticated=False)
    return jsonify(authenticated=True, role=role)


# -----------------------------------------------------------------------
# Per-role handlers
# -----------------------------------------------------------------------

def _login_admin(username: str, password: str):
    # Reuses your existing utils.verify_admin — identical logic to
    # whatever blueprints/admin.py's HTML-form login route already does.
    if verify_admin(username, password):
        session.clear()
        session["role"] = "admin"
        session["admin_user"] = username
        print("SESSION AFTER LOGIN:", dict(session))
        return jsonify(success=True, redirectUrl="/portal/admin/dashboard")

    return jsonify(success=False, message="Invalid admin username or password."), 401


def _login_student(register_number: str, password: str):
    from models import Student  # local import: avoids circular import at module load
    from werkzeug.security import generate_password_hash

    # Try database first
    student = Student.query.filter_by(register_number=register_number).first()
    
    if student is None:
        return jsonify(success=False, message="Invalid register number or password."), 401
    
    stored_password = student.password or ""
    
    # Handle hashed passwords (post-reset)
    if stored_password.startswith("pbkdf2:") or stored_password.startswith("scrypt:"):
        if not check_password_hash(stored_password, password):
            return jsonify(success=False, message="Invalid register number or password."), 401
    else:
        # Plain-text password check
        if password != stored_password:
            return jsonify(success=False, message="Invalid register number or password."), 401

    session.clear()
    session["role"] = "student"
    session["student_reg_no"] = register_number

    must_reset = password == DEFAULT_STUDENT_PASSWORD
    return jsonify(
        success=True,
        redirectUrl="/student/dashboard",
        mustResetPassword=must_reset,
    )


def _login_company(email: str, password: str):
    from models import CompanyHR  # uses the actual company HR model in your codebase

    company = CompanyHR.query.filter_by(email=email).first()
    if company is None or not check_password_hash(company.password_hash, password):
        return jsonify(success=False, message="Invalid email or password."), 401

    session.clear()
    session["role"] = "company"
    session["company_email"] = email
    session["company_name"] = company.company_name
    session["hr_name"] = company.hr_name
    return jsonify(success=True, redirectUrl="/company/dashboard")
