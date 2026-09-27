"""
blueprints/api_certificates.py
-----------------------------------------------------------------------------
NEW blueprint — JSON endpoints for React Certificate Management, built by
reusing the EXACT SAME logic blueprints/admin.py already uses in
admin_certificates() and review_certificate() (DB-first with CSV fallback,
and the same "bump Number_of_Certifications + append to Certifications_List
+ recompute skill_index" side effect on approval). No new business logic.

Register in app_new.py the same way api_students_bp was registered:
    from blueprints.api_certificates import api_certificates_bp
    app.register_blueprint(api_certificates_bp, url_prefix="/api/admin/certificates")

File viewing reuses the EXISTING route already registered under admin_bp:
    GET /admin/certificates/view/<filename>
so it is NOT duplicated here — the frontend links straight to that route.
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify, session
import pandas as pd

from auth_decorators import admin_required
from utils import read_master_df, save_master_df, compute_skill_index_for_row

api_certificates_bp = Blueprint("api_certificates", __name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CERT_CSV = os.path.join(DATA_DIR, "certificates.csv")


def _load_certificates():
    """DB-first / CSV-fallback — always returns (list, bool).
    
    student_portal.py writes uploads to CSV only (not the DB), so when the
    DB is available we merge DB rows + any CSV-only rows so nothing is lost.
    """
    db_records = []
    db_ok = False
    try:
        from models import Certificate
        objs = Certificate.query.order_by(Certificate.id.desc()).all()
        db_records = [
            {
                "certificate_id": c.certificate_id,
                "register_number": c.register_number,
                "student_name": c.student_name,
                "certificate_name": c.certificate_name,
                "file_path": c.file_path or "",
                "status": c.status,
                "uploaded_at": c.uploaded_at or "",
                "reviewed_by": c.reviewed_by or "",
                "reviewed_at": c.reviewed_at or "",
                "remarks": c.remarks or "",
            }
            for c in objs
        ]
        db_ok = True
    except Exception:
        pass

    # Always read CSV so uploads from student_portal (CSV-only) are visible.
    csv_records = []
    if os.path.exists(CERT_CSV):
        try:
            df = pd.read_csv(CERT_CSV)
            df.columns = df.columns.str.strip()
            if "file_path" not in df.columns:
                df["file_path"] = ""
            df["file_path"] = df["file_path"].fillna("").astype(str).str.strip()
            df["certificate_id"] = (
                pd.to_numeric(df["certificate_id"], errors="coerce")
                .fillna(0).astype(int)
            )
            # Fill any missing columns with empty string to keep a uniform shape
            for col in ["reviewed_by", "reviewed_at", "remarks", "student_name"]:
                if col not in df.columns:
                    df[col] = ""
            df = df.fillna("")
            csv_records = df.to_dict(orient="records")
        except Exception:
            pass

    if not db_ok:
        return csv_records, False

    # DB is available — merge: DB records take precedence; add any CSV rows
    # whose certificate_id isn't already in the DB result set.
    db_ids = {str(r["certificate_id"]) for r in db_records}
    extra = [
        r for r in csv_records
        if str(r["certificate_id"]) not in db_ids
    ]
    return db_records + extra, True


@api_certificates_bp.get("")
@admin_required
def list_certificates():
    """
    Mirrors admin.admin_certificates(), extended with an optional
    ?status= filter (defaults to 'pending' to match the old page's
    behaviour exactly; pass status=all to see everything).
    """
    certs, _ = _load_certificates()
    status_filter = request.args.get("status", "pending").strip().lower()

    if status_filter != "all":
        # Case-insensitive comparison — student_portal writes "pending",
        # the DB model default is "Pending"; both must match.
        certs = [c for c in certs if str(c.get("status", "")).strip().lower() == status_filter]

    return jsonify(success=True, certificates=certs)


@api_certificates_bp.post("/<int:cert_id>/review")
@admin_required
def review_certificate(cert_id):
    """Mirrors admin.review_certificate() exactly — same DB write, same
    CSV mirror, same on-approval student-record update."""
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    remarks = data.get("remarks", "")

    if action not in ("approve", "reject"):
        return jsonify(success=False, message="Invalid action."), 400

    new_status = "approved" if action == "approve" else "rejected"
    reviewed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    reviewer = session["admin_user"]

    reg_no = None
    cert_name = None
    db_used = False

    try:
        from models import Certificate, db
        cert_obj = Certificate.query.filter_by(certificate_id=str(cert_id)).first()
        if cert_obj:
            cert_obj.status = new_status
            cert_obj.reviewed_by = reviewer
            cert_obj.reviewed_at = reviewed_at
            cert_obj.remarks = remarks
            db.session.commit()
            reg_no = cert_obj.register_number
            cert_name = cert_obj.certificate_name
            db_used = True
        else:
            return jsonify(success=False, message="Certificate not found."), 404
    except Exception:
        pass

    if os.path.exists(CERT_CSV):
        try:
            df = pd.read_csv(CERT_CSV)
            idx = df[df["certificate_id"] == cert_id].index
            if not idx.empty:
                df.at[idx[0], "status"] = new_status
                df.at[idx[0], "reviewed_by"] = reviewer
                df.at[idx[0], "reviewed_at"] = reviewed_at
                df.at[idx[0], "remarks"] = remarks
                if not db_used:
                    reg_no = str(df.at[idx[0], "register_number"])
                    cert_name = df.at[idx[0], "certificate_name"]
                df.to_csv(CERT_CSV, index=False)
        except Exception:
            pass

    if not db_used and reg_no is None:
        return jsonify(success=False, message="Certificate not found."), 404

    if action == "approve" and reg_no and cert_name:
        master = read_master_df()
        stu_idx = master[master["Register_Number"].astype(str) == str(reg_no)].index
        if not stu_idx.empty:
            sidx = stu_idx[0]
            try:
                current = int(master.at[sidx, "Number_of_Certifications"])
            except Exception:
                current = 0
            master.at[sidx, "Number_of_Certifications"] = current + 1

            old = str(master.at[sidx, "Certifications_List"]).strip()
            master.at[sidx, "Certifications_List"] = (
                old + ", " + cert_name if old and old.lower() != "nan" else cert_name
            )
            master.at[sidx, "skill_index"] = compute_skill_index_for_row(master.loc[sidx])
            save_master_df(master)

    return jsonify(success=True, message=f"Certificate {action}d successfully.")
