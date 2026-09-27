"""
blueprints/api_CompanyManagement.py
-----------------------------------------------------------------------------
Placement Cell Control Center REST APIs for Admin Portal.

Features:
- Drive listing & detail viewing (drives originate only from Company Portal).
- Drive status approval/rejection (HR submission gate).
- Eligible Students evaluation: filters CGPA >= min_cgpa, sorts by skill_index descending.
- Student Assignment: approve/reject individual student allocations for a drive via drive_assignments.json.
- Available Tests listing: scans data/tests/*.csv.
- Test Assignment: assigns test links to rounds in data/company_drives.csv.
"""

from flask import Blueprint, jsonify, request
from auth_decorators import admin_required
from utils import read_master_df
from datetime import datetime
import pandas as pd
import json
import os

try:
    from models import db, Drive
    DB_ENABLED = True
except Exception:
    DB_ENABLED = False

api_companymanage_bp = Blueprint(
    "api_companymanage",
    __name__,
    url_prefix="/api/company"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
TESTS_DIR = os.path.join(DATA_DIR, "tests")

DRIVES_CSV = os.path.join(DATA_DIR, "company_drives.csv")
STATUS_JSON = os.path.join(DATA_DIR, "drive_status.json")
ASSIGNMENTS_JSON = os.path.join(DATA_DIR, "drive_assignments.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TESTS_DIR, exist_ok=True)


# -------------------------------------------------------
# Sidecar Loaders & Savers
# -------------------------------------------------------

def load_status_map():
    if not os.path.exists(STATUS_JSON):
        return {}
    try:
        with open(STATUS_JSON, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_status_map(status_map):
    with open(STATUS_JSON, "w") as f:
        json.dump(status_map, f, indent=2)


def load_assignments():
    if not os.path.exists(ASSIGNMENTS_JSON):
        return {}
    try:
        with open(ASSIGNMENTS_JSON, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_assignments(assignments):
    with open(ASSIGNMENTS_JSON, "w") as f:
        json.dump(assignments, f, indent=2)


# -------------------------------------------------------
# Load Drives (DB -> CSV fallback), status & assignments merged in
# -------------------------------------------------------

def load_drives():
    status_map = load_status_map()
    assignments_map = load_assignments()

    if DB_ENABLED:
        try:
            db_drives = Drive.query.order_by(Drive.created_at.desc()).all()
            rows = []
            for d in db_drives:
                did_str = str(d.drive_id)
                drive_assigns = assignments_map.get(did_str, {})
                approved_count = sum(1 for v in drive_assigns.values() if v.get("status") == "approved")
                rows.append({
                    "id": d.drive_id,
                    "company": d.company_name or "",
                    "role": d.position or "",
                    "package": d.package or "",
                    "duration": d.time_period or "",
                    "required": d.number_required or 0,
                    "cgpa": d.min_cgpa or 0.0,
                    "domain": d.domain_required or "",
                    "description": d.description or "",
                    "mode": d.mode or "",
                    "location": d.location or "",
                    "deadline": d.end_date or "",
                    "created_at": d.created_at or "",
                    "hr_email": d.hr_email or "",
                    "status": status_map.get(did_str, "Pending"),
                    "approved_count": approved_count,
                    "assignments": drive_assigns,
                })
            return pd.DataFrame(rows)
        except Exception:
            pass

    if os.path.exists(DRIVES_CSV):
        df = pd.read_csv(DRIVES_CSV)
        if not df.empty and "id" in df.columns:
            df["status"] = df["id"].astype(str).map(lambda i: status_map.get(i, "Pending"))
            df["assignments"] = df["id"].astype(str).map(lambda i: assignments_map.get(i, {}))
            df["approved_count"] = df["assignments"].map(
                lambda m: sum(1 for v in m.values() if v.get("status") == "approved") if isinstance(m, dict) else 0
            )
        return df

    return pd.DataFrame()


# -------------------------------------------------------
# Dashboard Summary
# -------------------------------------------------------

@api_companymanage_bp.get("/dashboard")
@admin_required
def dashboard():
    df = load_drives()
    if df.empty:
        return jsonify({"summary": {"total_drives": 0, "active_drives": 0, "companies": 0, "students": 0}})

    total_students = 0
    if "required" in df.columns:
        total_students = pd.to_numeric(df["required"], errors="coerce").fillna(0).sum()

    active_drives = len(df[df["status"] == "Approved"]) if "status" in df.columns else len(df)

    return jsonify({
        "summary": {
            "total_drives": len(df),
            "active_drives": active_drives,
            "companies": df["company"].nunique() if "company" in df.columns else 0,
            "students": int(total_students),
        }
    })


# -------------------------------------------------------
# All Drives
# -------------------------------------------------------

@api_companymanage_bp.get("/drives")
@admin_required
def all_drives():
    df = load_drives()
    if df.empty:
        return jsonify({"drives": []})

    drives = []
    for _, row in df.iterrows():
        assigns = row.get("assignments", {})
        if not isinstance(assigns, dict):
            assigns = {}
        drives.append({
            "id": int(row.get("id", 0)),
            "company": str(row.get("company", "")),
            "role": str(row.get("role", "")),
            "package": str(row.get("package", "")),
            "duration": str(row.get("duration", "")),
            "required": int(row.get("required", 0) or 0),
            "cgpa": float(row.get("cgpa", 0) or 0),
            "domain": str(row.get("domain", "")),
            "mode": str(row.get("mode", "")),
            "location": str(row.get("location", "")),
            "deadline": str(row.get("deadline", "")),
            "description": str(row.get("description", "")),
            "created_at": str(row.get("created_at", "")),
            "status": str(row.get("status", "Pending")),
            "approved_count": int(row.get("approved_count", 0) or 0),
            "assignments": assigns,
            "aptitude_test_link": str(row.get("aptitude_test_link", "") or ""),
            "domain_test_link": str(row.get("domain_test_link", "") or ""),
            "coding_test_link": str(row.get("coding_test_link", "") or ""),
        })
    return jsonify({"drives": drives})


# -------------------------------------------------------
# Single Drive Details
# -------------------------------------------------------

@api_companymanage_bp.get("/drives/<int:drive_id>")
@admin_required
def drive_details(drive_id):
    df = load_drives()
    if df.empty:
        return jsonify({"message": "Drive not found"}), 404

    drive = df[df["id"] == drive_id]
    if drive.empty:
        return jsonify({"message": "Drive not found"}), 404

    row = drive.iloc[0]
    assigns = row.get("assignments", {})
    if not isinstance(assigns, dict):
        assigns = {}

    return jsonify({
        "id": int(row["id"]),
        "company": str(row["company"]),
        "role": str(row["role"]),
        "package": str(row["package"]),
        "duration": str(row["duration"]),
        "required": int(row["required"] or 0),
        "cgpa": float(row["cgpa"] or 0),
        "domain": str(row["domain"]),
        "description": str(row["description"]),
        "mode": str(row["mode"]),
        "location": str(row["location"]),
        "deadline": str(row["deadline"]),
        "created_at": str(row["created_at"]),
        "status": str(row.get("status", "Pending")),
        "approved_count": int(row.get("approved_count", 0) or 0),
        "assignments": assigns,
        "aptitude_test_link": str(row.get("aptitude_test_link", "") or ""),
        "domain_test_link": str(row.get("domain_test_link", "") or ""),
        "coding_test_link": str(row.get("coding_test_link", "") or ""),
    })


# -------------------------------------------------------
# Drive HR Submission Gate (Approve / Reject Drive)
# -------------------------------------------------------

@api_companymanage_bp.post("/drives/<int:drive_id>/approve")
@admin_required
def approve_drive(drive_id):
    return _set_status(drive_id, "Approved")


@api_companymanage_bp.post("/drives/<int:drive_id>/reject")
@admin_required
def reject_drive(drive_id):
    return _set_status(drive_id, "Rejected")


def _set_status(drive_id, new_status):
    df = load_drives()
    if df.empty or df[df["id"] == drive_id].empty:
        return jsonify(success=False, message="Drive not found."), 404

    status_map = load_status_map()
    status_map[str(drive_id)] = new_status
    save_status_map(status_map)

    return jsonify(success=True, message=f"Drive {new_status.lower()}.", status=new_status)


# -------------------------------------------------------
# Eligible Students Engine
# -------------------------------------------------------

@api_companymanage_bp.get("/drives/<int:drive_id>/eligible-students")
@admin_required
def get_eligible_students(drive_id):
    """
    Evaluates students for candidate allocation using verified fields:
    - CGPA >= drive.min_cgpa
    - Optional Department filter match
    - Sorted by skill_index descending
    - Includes assignment status from drive_assignments.json
    """
    df_drives = load_drives()
    if df_drives.empty or df_drives[df_drives["id"] == drive_id].empty:
        return jsonify(success=False, message="Drive not found."), 404

    drive = df_drives[df_drives["id"] == drive_id].iloc[0]
    min_cgpa = float(drive.get("cgpa", 0.0) or 0.0)
    domain_req = str(drive.get("domain", "")).strip().lower()
    drive_required = int(drive.get("required", 0) or 0)

    # Optional department override filter
    dept_filter = str(request.args.get("department", "")).strip()

    assignments_map = load_assignments()
    drive_assignments = assignments_map.get(str(drive_id), {})

    df_students = read_master_df()
    if df_students.empty:
        return jsonify({"students": [], "summary": {"total_eligible": 0, "required": drive_required, "min_cgpa": min_cgpa}})

    eligible_students = []
    for _, s in df_students.iterrows():
        reg_no = str(s.get("Register_Number", "")).strip()
        if not reg_no:
            continue

        try:
            cgpa = float(s.get("CGPA", 0.0) or 0.0)
        except (ValueError, TypeError):
            cgpa = 0.0

        if cgpa < min_cgpa:
            continue

        dept = str(s.get("Department", "General")).strip()
        if dept_filter and dept.lower() != dept_filter.lower():
            continue

        try:
            skill_idx = float(s.get("skill_index", 0.0) or 0.0)
        except (ValueError, TypeError):
            skill_idx = 0.0

        current_record = drive_assignments.get(reg_no, {})
        assign_status = current_record.get("status", "pending")

        eligible_students.append({
            "register_number": reg_no,
            "student_name": str(s.get("Student_Name", "Unknown")),
            "department": dept,
            "batch": str(s.get("Batch", "N/A")),
            "cgpa": round(cgpa, 2),
            "skill_index": round(skill_idx, 2),
            "assignment_status": assign_status,
            "assigned_at": current_record.get("assigned_at"),
        })

    # Sort by skill_index descending
    eligible_students.sort(key=lambda x: (x["assignment_status"] == "approved", x["skill_index"], x["cgpa"]), reverse=True)

    approved_count = sum(1 for s in eligible_students if s["assignment_status"] == "approved")

    return jsonify({
        "students": eligible_students,
        "summary": {
            "total_eligible": len(eligible_students),
            "approved_count": approved_count,
            "required_capacity": drive_required,
            "min_cgpa": min_cgpa,
        }
    })


# -------------------------------------------------------
# Candidate Assignment Action
# -------------------------------------------------------

@api_companymanage_bp.post("/drives/<int:drive_id>/assign")
@admin_required
def assign_student(drive_id):
    """
    Body: { register_number: string, status: "approved" | "rejected" | "pending" }
    Writes candidate allocation status to drive_assignments.json.
    """
    df_drives = load_drives()
    if df_drives.empty or df_drives[df_drives["id"] == drive_id].empty:
        return jsonify(success=False, message="Drive not found."), 404

    data = request.get_json(silent=True) or {}
    reg_no = str(data.get("register_number", "")).strip()
    status = str(data.get("status", "approved")).strip().lower()

    if not reg_no:
        return jsonify(success=False, message="Register number is required."), 400

    if status not in ("approved", "rejected", "pending"):
        return jsonify(success=False, message="Invalid status. Must be approved, rejected, or pending."), 400

    assignments_map = load_assignments()
    did_str = str(drive_id)
    if did_str not in assignments_map:
        assignments_map[did_str] = {}

    if status == "pending":
        assignments_map[did_str].pop(reg_no, None)
    else:
        assignments_map[did_str][reg_no] = {
            "status": status,
            "assigned_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "assigned_by": "admin"
        }

    save_assignments(assignments_map)

    approved_count = sum(1 for v in assignments_map[did_str].values() if v.get("status") == "approved")

    return jsonify({
        "success": True,
        "message": f"Student {reg_no} marked as {status}.",
        "register_number": reg_no,
        "status": status,
        "approved_count": approved_count,
    })


# -------------------------------------------------------
# Available Tests Listing
# -------------------------------------------------------

@api_companymanage_bp.get("/available-tests")
@admin_required
def available_tests():
    """Lists all assessment CSV files available in data/tests/."""
    tests = []
    if os.path.exists(TESTS_DIR):
        for f in os.listdir(TESTS_DIR):
            if f.endswith(".csv"):
                clean_name = f.replace(".csv", "").replace("_", " ").title()
                tests.append({
                    "filename": f,
                    "name": clean_name,
                })

    return jsonify({"tests": tests})


# -------------------------------------------------------
# Test Assignment Action
# -------------------------------------------------------

@api_companymanage_bp.post("/drives/<int:drive_id>/assign-test")
@admin_required
def assign_test(drive_id):
    """
    Body: { round: "aptitude" | "domain" | "coding", filename: string, duration?: number }
    Writes internal test link directly to data/company_drives.csv.
    """
    if not os.path.exists(DRIVES_CSV):
        return jsonify(success=False, message="No drives on record."), 404

    data = request.get_json(silent=True) or {}
    round_type = str(data.get("round", "aptitude")).strip().lower()
    filename = str(data.get("filename", "")).strip()
    duration = data.get("duration", 30)

    if round_type not in ("aptitude", "domain", "coding"):
        return jsonify(success=False, message="Invalid round type. Must be aptitude, domain, or coding."), 400

    df = pd.read_csv(DRIVES_CSV)
    idx = df[df["id"] == drive_id].index
    if idx.empty:
        return jsonify(success=False, message="Drive not found."), 404

    sidx = idx[0]
    link_col = f"{round_type}_test_link"
    dur_col = f"{round_type}_duration"

    test_link_val = f"internal:{filename}" if filename else ""

    df.at[sidx, link_col] = test_link_val
    df.at[sidx, dur_col] = duration

    df.to_csv(DRIVES_CSV, index=False)

    return jsonify({
        "success": True,
        "message": f"{round_type.title()} test assigned successfully.",
        "round": round_type,
        "test_link": test_link_val,
        "duration": duration,
    })
