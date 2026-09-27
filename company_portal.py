from flask import Flask, render_template, request, redirect, url_for, flash, session
import pandas as pd
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMPANY_DATA = os.path.join(BASE_DIR, "data", "company_hr.json")
DRIVES_DATA = os.path.join(BASE_DIR, "data", "company_drives.csv")

app = Flask(__name__)
app.secret_key = "company_portal_secret_123"

# -------------------------------------------------------
# Helper Functions
# -------------------------------------------------------

def load_company_data():
    if os.path.exists(COMPANY_DATA):
        return pd.read_json(COMPANY_DATA)
    return pd.DataFrame(columns=["company_name", "hr_name", "email", "phone", "position", "password_hash"])

def save_company_data(df):
    df.to_json(COMPANY_DATA, orient="records")

def load_drives():
    if os.path.exists(DRIVES_DATA):
        return pd.read_csv(DRIVES_DATA)
    return pd.DataFrame(columns=[
        "drive_id", 
        "hr_email", 
        "company_name", 
        "position", 
        "package",
        "time_period", 
        "number_required", 
        "min_cgpa",
        "domain_required",     # ← UPDATED
        "description", 
        "mode", 
        "location", 
        "end_date", 
        "created_at"
    ])


def save_drives(df):
    df.to_csv(DRIVES_DATA, index=False)

# -------------------------------------------------------
# Company HR Signup
# -------------------------------------------------------
@app.route("/")
def home():
    return redirect("/company/login")

@app.route("/company/signup", methods=["GET", "POST"])
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
            return redirect(url_for('company_signup'))

        hashed = generate_password_hash(password)

        df.loc[len(df)] = [company_name, hr_name, email, phone, position, hashed]
        save_company_data(df)

        flash("Account created! Please login.", "success")
        return redirect(url_for('company_login'))

    return render_template("company_signup.html")

# -------------------------------------------------------
# Company HR Login
# -------------------------------------------------------

@app.route("/company/login", methods=["GET", "POST"])
def company_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        df = load_company_data()
        user = df[df["email"] == email]

        if user.empty:
            flash("Invalid email or password", "danger")
            return redirect(url_for("company_login"))

        if not check_password_hash(user.iloc[0]["password_hash"], password):
            flash("Wrong password", "danger")
            return redirect(url_for("company_login"))

        # Set session
        session["company_email"] = email
        session["company_name"] = user.iloc[0]["company_name"]
        session["hr_name"] = user.iloc[0]["hr_name"]

        return redirect(url_for("company_dashboard"))

    return render_template("company_login.html")

# -------------------------------------------------------
# Dashboard
# -------------------------------------------------------

@app.route("/company/dashboard")
def company_dashboard():
    if "company_email" not in session:
        return redirect(url_for("company_login"))

    drives = load_drives()
    user_drives = drives[drives["hr_email"] == session["company_email"]]

    return render_template("company_dashboard.html", drives=user_drives)

# -------------------------------------------------------
# Create Drive
# -------------------------------------------------------

@app.route("/company/create_drive", methods=["GET", "POST"])
def create_drive():
    if "company_email" not in session:
        return redirect(url_for("company_login"))

    if request.method == "POST":
        form = request.form

        df = load_drives()

        drive_id = len(df) + 1
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Build package from two fields
        package_value = form.get("package_value", "")
        package_type = form.get("package_type", "")
        package = f"{package_value} {package_type}".strip()

        # Read domain correctly (not skills_required)
        domain = form.get("domain_required", "")

        df.loc[len(df)] = [
            drive_id,
            session["company_email"],
            session["company_name"],
            form.get("position", ""),
            package,                    # ← FIXED
            form.get("time_period", ""),
            form.get("number_required", ""),
            form.get("min_cgpa", ""),
            domain,                    # ← FIXED
            form.get("description", ""),
            form.get("mode", ""),
            form.get("location", ""),
            form.get("end_date", ""),
            created_at
        ]

        save_drives(df)

        flash("Drive created successfully!", "success")
        return redirect(url_for("company_dashboard"))

    return render_template("company_create_drive.html")


# -------------------------------------------------------
# Logout
# -------------------------------------------------------

@app.route("/company/logout")
def company_logout():
    session.clear()
    return redirect(url_for("company_login"))


if __name__ == "__main__":
    app.run(debug=True, port=5003)

