"""
blueprints/api_admin.py
-----------------------------------------------------------------------------
NEW blueprint — read-only JSON endpoints for the admin dashboard. Register
this the same way api_auth_bp is registered (see app_new.py note below).

Built directly against your real models.py, so these field names are
CONFIRMED, not guessed:
  Student(is_active, skill_level, department, ...)
  CompanyHR(company_name, ...)
  Drive(id, created_at, ...)
  Certificate(status, uploaded_at, student_name, certificate_name, ...)
  TestResult(...)

Protected with @admin_required from auth_decorators.py — same session
check as your existing HTML admin routes.
"""

from flask import Blueprint, jsonify
from auth_decorators import admin_required
from models import db, Student, CompanyHR, Drive, Certificate, TestResult

api_admin_bp = Blueprint("api_admin", __name__)


@api_admin_bp.get("/dashboard-stats")
@admin_required
def dashboard_stats():
    total_students = Student.query.filter_by(is_active=True).count()
    total_companies = CompanyHR.query.count()
    total_drives = Drive.query.count()
    pending_certificates = Certificate.query.filter_by(status="Pending").count()
    approved_certificates = Certificate.query.filter_by(status="Approved").count()
    total_test_attempts = TestResult.query.count()

    # Skill level breakdown — powers the donut chart
    skill_rows = (
        db.session.query(Student.skill_level, db.func.count(Student.id))
        .filter(Student.is_active == True)  # noqa: E712
        .group_by(Student.skill_level)
        .all()
    )
    skill_breakdown = [{"level": lvl or "Unrated", "count": cnt} for lvl, cnt in skill_rows]

    # Department headcount — powers the bar chart
    dept_rows = (
        db.session.query(Student.department, db.func.count(Student.id))
        .filter(Student.is_active == True)  # noqa: E712
        .group_by(Student.department)
        .all()
    )
    department_breakdown = [{"department": d or "Unknown", "count": c} for d, c in dept_rows]

    # Recent activity — latest 6 certificate submissions
    recent_certs = (
        Certificate.query.order_by(Certificate.uploaded_at.desc()).limit(6).all()
    )
    recent_activity = [
        {
            "id": c.certificate_id,
            "studentName": c.student_name,
            "certificateName": c.certificate_name,
            "status": c.status,
            "uploadedAt": c.uploaded_at,
        }
        for c in recent_certs
    ]

    return jsonify(
        totals={
            "students": total_students,
            "companies": total_companies,
            "drives": total_drives,
            "pendingCertificates": pending_certificates,
            "approvedCertificates": approved_certificates,
            "testAttempts": total_test_attempts,
        },
        skillBreakdown=skill_breakdown,
        departmentBreakdown=department_breakdown,
        recentActivity=recent_activity,
    )
