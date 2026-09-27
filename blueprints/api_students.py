"""
blueprints/api_students.py
-----------------------------------------------------------------------------
NEW blueprint — JSON endpoints for React Student Management, built by
reusing the EXACT SAME functions blueprints/admin.py already uses
(read_master_df, save_master_df, read_recycle_df, save_recycle_df) —
not the SQLAlchemy Student model, since admin.py never touches it for
student CRUD. This keeps React in sync with the same CSV-backed data
your existing HTML admin pages already read/write.

Register in app_new.py the same way as api_admin_bp:
    from blueprints.api_students import api_students_bp
    app.register_blueprint(api_students_bp, url_prefix="/api/admin/students")

⚠️ "Edit a single student" has NO equivalent in admin.py today (only bulk
CSV re-upload via merge_upload_df exists) — not implemented here. Confirm
what you want before I add it, since it'd be new logic, not reused logic.
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify, session
import pandas as pd

from auth_decorators import admin_required
from utils import (
    read_master_df, save_master_df, read_recycle_df, save_recycle_df,
    merge_upload_df, compute_skill_index_for_row,
)

api_students_bp = Blueprint("api_students", __name__)


def _nan_safe(obj):
    """Recursively replace float NaN / Inf with None so jsonify never
    emits the bare token NaN, which is not valid JSON."""
    import math
    if isinstance(obj, list):
        return [_nan_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _nan_safe(v) for k, v in obj.items()}
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CERT_CSV = os.path.join(DATA_DIR, "certificates.csv")

DEFAULT_STUDENT_PASSWORD = "helloeveryone"

# Core, manually-editable fields for single Add/Edit. master_students.csv
# has ~80 columns total (per-semester subjects/grades, certifications,
# etc.) — those still only come in via bulk CSV upload. Add/Edit covers
# the fields an admin would realistically type by hand; everything else
# defaults blank/zero on create and is left untouched on edit.
CORE_STUDENT_FIELDS = [
    "Register_Number", "Student_Name", "Department", "Batch",
    "Gender", "Current_Sem", "CGPA",
]


@api_students_bp.get("")
@admin_required
def list_students():
    """
    Mirrors admin.py's view_students() GET filters exactly (batch, dept,
    current_sem, cgpa_filter_type/cgpa_value), plus adds free-text search
    by name or register number — a new capability layered on the same
    read-only data source, not a change to any existing write logic.
    """
    df = read_master_df()
    if df.empty:
        return jsonify(students=[], batches=[], departments=[], semesters=[])

    batches = sorted(df["Batch"].dropna().unique().tolist())
    departments = sorted(df["Department"].dropna().unique().tolist())
    semesters = sorted(df["Current_Sem"].dropna().unique().tolist())

    filtered = df.copy()

    batch = request.args.get("batch")
    dept = request.args.get("dept")
    sem = request.args.get("current_sem")
    cgpa_type = request.args.get("cgpa_filter_type")
    cgpa_value = request.args.get("cgpa_value")
    search = request.args.get("search", "").strip().lower()
    sort_by = request.args.get("sort_by", "Student_Name")
    sort_dir = request.args.get("sort_dir", "asc")

    if batch and batch != "all":
        filtered = filtered[filtered["Batch"] == batch]
    if dept and dept != "all":
        filtered = filtered[filtered["Department"] == dept]
    if sem and sem != "all":
        filtered = filtered[filtered["Current_Sem"] == int(sem)]
    if cgpa_type and cgpa_value:
        try:
            cgpa_value = float(cgpa_value)
            if cgpa_type == "greater":
                filtered = filtered[filtered["CGPA"] > cgpa_value]
            elif cgpa_type == "less":
                filtered = filtered[filtered["CGPA"] < cgpa_value]
        except ValueError:
            pass
    if search:
        filtered = filtered[
            filtered["Student_Name"].astype(str).str.lower().str.contains(search)
            | filtered["Register_Number"].astype(str).str.lower().str.contains(search)
        ]

    if sort_by in filtered.columns:
        filtered = filtered.sort_values(by=sort_by, ascending=(sort_dir != "desc"))

    keep_cols = [
        "Register_Number", "Student_Name", "Department", "Batch",
        "Current_Sem", "CGPA", "skill_index", "skill_level",
    ]
    keep_cols = [c for c in keep_cols if c in filtered.columns]
    students = _nan_safe(filtered[keep_cols].to_dict(orient="records"))

    return jsonify(
        students=students,
        batches=batches,
        departments=departments,
        semesters=semesters,
    )


@api_students_bp.get("/<reg_no>")
@admin_required
def student_detail(reg_no):
    """Mirrors admin.py's student_profile() — full row for one student,
    plus that student's certificates (new: admin.py's certificate view
    only ever lists ALL pending certs, never scoped to one student)."""
    df = read_master_df()
    if df.empty:
        return jsonify(success=False, message="No student data available."), 404

    reg_no = str(reg_no)
    row = df[df["Register_Number"].astype(str).str.strip() == reg_no.strip()]
    if row.empty:
        return jsonify(success=False, message="Student not found."), 404

    student = _nan_safe(row.to_dict(orient="records")[0])

    certificates = []
    if os.path.exists(CERT_CSV):
        try:
            cert_df = pd.read_csv(CERT_CSV)
            cert_df.columns = cert_df.columns.str.strip()
            mine = cert_df[cert_df["register_number"].astype(str) == reg_no]
            certificates = mine.to_dict(orient="records")
        except Exception:
            certificates = []

    return jsonify(success=True, student=student, certificates=certificates)


@api_students_bp.post("/delete")
@admin_required
def delete_students():
    """Mirrors admin.py's delete_students() exactly — moves selected
    students to recycle_bin.csv rather than hard-deleting."""
    data = request.get_json(silent=True) or {}
    regs = data.get("registers") or []
    if not regs:
        return jsonify(success=False, message="No students selected."), 400

    master = read_master_df()
    recycle = read_recycle_df()
    moved = []

    for reg in regs:
        idx = master[master["Register_Number"].astype(str) == str(reg)].index
        if not idx.empty:
            row = master.loc[idx[0]].to_dict()
            row["deleted_at"] = datetime.utcnow().isoformat()
            row["deleted_by"] = session["admin_user"]
            recycle = pd.concat([recycle, pd.DataFrame([row])], ignore_index=True)
            master = master.drop(index=idx)
            moved.append(reg)

    save_master_df(master)
    save_recycle_df(recycle)

    return jsonify(success=True, message=f"Moved {len(moved)} student(s) to recycle bin.", moved=moved)


@api_students_bp.post("/upload")
@admin_required
def upload_students_csv():
    """Mirrors admin.py's add_students() POST branch exactly — same
    merge_upload_df() call, same success semantics, just JSON instead of
    a redirect+flash."""
    file = request.files.get("file")
    filename = getattr(file, "filename", "") if file is not None else ""
    if not filename or not filename.lower().endswith(".csv"):
        return jsonify(success=False, message="Please upload a CSV file."), 400

    try:
        df_upload = pd.read_csv(file)
        result = merge_upload_df(df_upload, session["admin_user"])
        return jsonify(success=True, message=f"Upload complete: {result['updated']} records updated.", result=result)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500


@api_students_bp.post("")
@admin_required
def create_student():
    """NEW — no equivalent in admin.py. Adds one row to master_students.csv
    with the core fields provided; all other columns default blank/0 and
    can be filled in later via bulk CSV upload."""
    data = request.get_json(silent=True) or {}
    reg_no = str(data.get("Register_Number", "")).strip()
    name = str(data.get("Student_Name", "")).strip()

    if not reg_no or not name:
        return jsonify(success=False, message="Register Number and Student Name are required."), 400

    master = read_master_df()
    if not master.empty and (master["Register_Number"].astype(str).str.strip() == reg_no).any():
        return jsonify(success=False, message="A student with this Register Number already exists."), 409

    new_row = {col: "" for col in (master.columns if not master.empty else CORE_STUDENT_FIELDS)}
    new_row.update({
        "Register_Number": reg_no,
        "Student_Name": name,
        "Department": data.get("Department", ""),
        "Batch": data.get("Batch", ""),
        "Gender": data.get("Gender", ""),
        "Current_Sem": data.get("Current_Sem", 1),
        "CGPA": data.get("CGPA", 0),
        "Password": data.get("Password") or DEFAULT_STUDENT_PASSWORD,
        "Number_of_Certifications": 0,
        "Projects_Done": 0,
        "Hackathons_Participated": 0,
    })

    master = pd.concat([master, pd.DataFrame([new_row])], ignore_index=True)

    try:
        idx = master.index[-1]
        master.at[idx, "skill_index"] = compute_skill_index_for_row(master.loc[idx])
    except Exception:
        pass  # skill index calc may need fields we don't collect here — safe to skip on create

    save_master_df(master)
    return jsonify(success=True, message="Student added.", student=new_row)


@api_students_bp.put("/<reg_no>")
@admin_required
def update_student(reg_no):
    """NEW — no equivalent in admin.py. Updates only the core fields
    provided; all other existing columns on that row are left untouched."""
    data = request.get_json(silent=True) or {}
    reg_no = str(reg_no).strip()

    master = read_master_df()
    idx = master[master["Register_Number"].astype(str).str.strip() == reg_no].index
    if idx.empty:
        return jsonify(success=False, message="Student not found."), 404

    sidx = idx[0]
    for field in CORE_STUDENT_FIELDS:
        if field in data and field != "Register_Number":  # register number is the lookup key, not editable
            master.at[sidx, field] = data[field]

    try:
        master.at[sidx, "skill_index"] = compute_skill_index_for_row(master.loc[sidx])
    except Exception:
        pass

    save_master_df(master)
    return jsonify(success=True, message="Student updated.")