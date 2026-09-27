from auth_decorators import company_required
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import pandas as pd
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

company_bp = Blueprint("company", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPANY_DATA = os.path.join(BASE_DIR, "data", "company_hr.json")
DRIVES_DATA = os.path.join(BASE_DIR, "data", "company_drives.csv")


def _db_ok():
    try:
        from models import CompanyHR, db
        db.session.execute(db.select(CompanyHR).limit(1))
        return True
    except Exception:
        return False


def load_company_data():
    """Return company HR records as a DataFrame."""
    if _db_ok():
        from models import CompanyHR
        rows = [{"company_name": h.company_name, "hr_name": h.hr_name,
                 "email": h.email, "phone": h.phone,
                 "position": h.position, "password_hash": h.password_hash}
                for h in CompanyHR.query.all()]
        return pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["company_name","hr_name","email","phone","position","password_hash"])
    if os.path.exists(COMPANY_DATA):
        return pd.read_json(COMPANY_DATA)
    return pd.DataFrame(columns=["company_name","hr_name","email","phone","position","password_hash"])


def save_company_data(df):
    """Upsert company HR records into DB (and mirror to JSON)."""
    if _db_ok():
        from models import CompanyHR, db
        for _, row in df.iterrows():
            email = str(row.get("email", "")).strip()
            if not email:
                continue
            existing = CompanyHR.query.filter_by(email=email).first()
            if existing:
                existing.company_name  = str(row.get("company_name", ""))
                existing.hr_name       = str(row.get("hr_name", ""))
                existing.phone         = str(row.get("phone", ""))
                existing.position      = str(row.get("position", ""))
                existing.password_hash = str(row.get("password_hash", ""))
            else:
                db.session.add(CompanyHR(
                    company_name=str(row.get("company_name", "")),
                    hr_name=str(row.get("hr_name", "")),
                    email=email,
                    phone=str(row.get("phone", "")),
                    position=str(row.get("position", "")),
                    password_hash=str(row.get("password_hash", "")),
                ))
        db.session.commit()
    df.to_json(COMPANY_DATA, orient="records")


def load_drives():
    """Return all drives as a DataFrame."""
    if _db_ok():
        from models import Drive
        rows = [{
            "drive_id": d.drive_id, "hr_email": d.hr_email,
            "company_name": d.company_name, "position": d.position,
            "package": d.package, "time_period": d.time_period,
            "number_required": d.number_required, "min_cgpa": d.min_cgpa,
            "domain_required": d.domain_required, "description": d.description,
            "mode": d.mode, "location": d.location,
            "end_date": d.end_date, "created_at": d.created_at,
        } for d in Drive.query.all()]
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
            "drive_id","hr_email","company_name","position","package",
            "time_period","number_required","min_cgpa","domain_required",
            "description","mode","location","end_date","created_at"])
    if os.path.exists(DRIVES_DATA):
        return pd.read_csv(DRIVES_DATA)
    return pd.DataFrame(columns=[
        "drive_id","hr_email","company_name","position","package",
        "time_period","number_required","min_cgpa","domain_required",
        "description","mode","location","end_date","created_at"])


def save_drives(df):
    """Upsert drives into DB and mirror to CSV."""
    if _db_ok():
        from models import Drive, db
        for _, row in df.iterrows():
            did = str(row.get("drive_id", "")).strip()
            if not did:
                continue
            d = Drive.query.filter_by(drive_id=did).first()
            def sv(col): v = row.get(col); return str(v) if pd.notna(v) else ""
            def fv(col): v = row.get(col); return float(v) if pd.notna(v) else 0
            def iv(col): v = row.get(col); return int(float(v)) if pd.notna(v) else 0
            if d:
                d.hr_email=sv("hr_email"); d.company_name=sv("company_name")
                d.position=sv("position"); d.package=sv("package")
                d.time_period=sv("time_period"); d.number_required=iv("number_required")
                d.min_cgpa=fv("min_cgpa"); d.domain_required=sv("domain_required")
                d.description=sv("description"); d.mode=sv("mode")
                d.location=sv("location"); d.end_date=sv("end_date"); d.created_at=sv("created_at")
            else:
                db.session.add(Drive(  # type: ignore[call-arg]
                    drive_id=did, hr_email=sv("hr_email"), company_name=sv("company_name"),
                    position=sv("position"), package=sv("package"), time_period=sv("time_period"),
                    number_required=iv("number_required"), min_cgpa=fv("min_cgpa"),
                    domain_required=sv("domain_required"), description=sv("description"),
                    mode=sv("mode"), location=sv("location"), end_date=sv("end_date"),
                    created_at=sv("created_at")))
        db.session.commit()
    df.to_csv(DRIVES_DATA, index=False)



# -----------------------------------------------
# AUTH
# -----------------------------------------------

@company_bp.route("/")
@company_bp.route("/login", methods=["GET", "POST"])
def company_login():
    # Redirect to React login page (new centralized login)
    if request.method == "GET":
        return redirect("/")


@company_bp.route("/signup", methods=["GET", "POST"])
def company_signup():
    if request.method == "POST":
        company_name = request.form["company_name"]
        hr_name = request.form["hr_name"]
        position = request.form["position"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        df = load_company_data()

        if email in df["email"].values:
            flash("Email already registered", "danger")
            return redirect(url_for("company.company_signup"))

        hashed = generate_password_hash(password)
        df.loc[len(df)] = [company_name, hr_name, email, phone, position, hashed]
        save_company_data(df)

        flash("Account created! Please login.", "success")
        return redirect(url_for("company.company_login"))

    return render_template("company_signup.html")


# -----------------------------------------------
# DASHBOARD
# -----------------------------------------------

@company_bp.route("/dashboard")
@company_required
def company_dashboard():
    drives = load_drives()
    user_drives = drives[drives["hr_email"] == session["company_email"]].copy()

    # Merge status and approved candidate allocations from sidecar
    assignments_json = os.path.join(BASE_DIR, "data", "drive_assignments.json")
    status_json = os.path.join(BASE_DIR, "data", "drive_status.json")

    assignments_map = {}
    status_map = {}
    if os.path.exists(assignments_json):
        try:
            with open(assignments_json, "r") as f: assignments_map = json.load(f)
        except Exception: pass
    if os.path.exists(status_json):
        try:
            with open(status_json, "r") as f: status_map = json.load(f)
        except Exception: pass

    if not user_drives.empty and "drive_id" in user_drives.columns:
        user_drives["status"] = user_drives["drive_id"].astype(str).map(lambda i: status_map.get(i, "Pending"))
        user_drives["approved_candidates"] = user_drives["drive_id"].astype(str).map(
            lambda i: [k for k, v in assignments_map.get(i, {}).items() if v.get("status") == "approved"]
        )
        user_drives["approved_count"] = user_drives["approved_candidates"].map(lambda lst: len(lst) if isinstance(lst, list) else 0)

    return render_template("company_dashboard.html", drives=user_drives)


# -----------------------------------------------
# CREATE DRIVE
# -----------------------------------------------

@company_bp.route("/create_drive", methods=["GET", "POST"])
@company_required
def create_drive():
    if request.method == "POST":
        form = request.form
        df = load_drives()

        drive_id = len(df) + 1
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        package_value = form.get("package_value", "")
        package_type = form.get("package_type", "")
        package = f"{package_value} {package_type}".strip()
        domain = form.get("domain_required", "")

        df.loc[len(df)] = [
            drive_id,
            session["company_email"],
            session["company_name"],
            form.get("position", ""),
            package,
            form.get("time_period", ""),
            form.get("number_required", ""),
            form.get("min_cgpa", ""),
            domain,
            form.get("description", ""),
            form.get("mode", ""),
            form.get("location", ""),
            form.get("end_date", ""),
            created_at
        ]

        save_drives(df)
        flash("Drive created successfully!", "success")
        return redirect(url_for("company.company_dashboard"))

    return render_template("company_create_drive.html")


# -----------------------------------------------
# LOGOUT
# -----------------------------------------------

@company_bp.route("/logout")
def company_logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect("/")  # Redirect to React login page
