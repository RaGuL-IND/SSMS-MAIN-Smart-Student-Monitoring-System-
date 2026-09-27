# =============================================================================
# db_init.py — One-time migration from CSV/JSON files → SQLite (portal.db)
# Run once:  python db_init.py
# Safe to re-run — skips rows that already exist.
# =============================================================================

import os, json, sys
import pandas as pd
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

MASTER_CSV  = os.path.join(DATA_DIR, "master_students.csv")
RECYCLE_CSV = os.path.join(DATA_DIR, "recycle_bin.csv")
CERT_CSV    = os.path.join(DATA_DIR, "certificates.csv")
DRIVES_CSV  = os.path.join(DATA_DIR, "company_drives.csv")
RESULTS_CSV = os.path.join(DATA_DIR, "test_results.csv")
ADMINS_JSON = os.path.join(DATA_DIR, "admins.json")
HR_JSON     = os.path.join(DATA_DIR, "company_hr.json")


def run_migration(app, db):
    """Call this inside an app context to migrate all CSV/JSON data to SQLite."""
    from models import Admin, Student, CompanyHR, Drive, Certificate, TestResult

    db.create_all()

    # ── 1. Admins ────────────────────────────────────────────────────────────
    if os.path.exists(ADMINS_JSON):
        admins = json.load(open(ADMINS_JSON, encoding="utf-8"))
        migrated = 0
        for username, pwd_hash in admins.items():
            if not Admin.query.filter_by(username=username).first():
                db.session.add(Admin(username=username, password_hash=pwd_hash))
                migrated += 1
        db.session.commit()
        print(f"  [Admins]      {migrated} migrated ({len(admins)} total)")

    # ── 2. Company HR ─────────────────────────────────────────────────────────
    if os.path.exists(HR_JSON):
        hr_list = json.load(open(HR_JSON, encoding="utf-8"))
        migrated = 0
        for hr in hr_list:
            if not CompanyHR.query.filter_by(email=hr.get("email")).first():
                db.session.add(CompanyHR(
                    company_name  = hr.get("company_name"),
                    hr_name       = hr.get("hr_name"),
                    email         = hr.get("email"),
                    phone         = str(hr.get("phone", "")),
                    position      = hr.get("position"),
                    password_hash = hr.get("password_hash"),
                ))
                migrated += 1
        db.session.commit()
        print(f"  [CompanyHR]   {migrated} migrated ({len(hr_list)} total)")

    # ── 3. Drives ─────────────────────────────────────────────────────────────
    if os.path.exists(DRIVES_CSV):
        df = pd.read_csv(DRIVES_CSV)
        migrated = 0
        for _, row in df.iterrows():
            did = str(row.get("drive_id", ""))
            if not Drive.query.filter_by(drive_id=did).first():
                db.session.add(Drive(
                    drive_id        = did,
                    hr_email        = str(row.get("hr_email", "")),
                    company_name    = str(row.get("company_name", "")),
                    position        = str(row.get("position", "")),
                    package         = str(row.get("package", "")),
                    time_period     = str(row.get("time_period", "")),
                    number_required = int(row.get("number_required", 0)) if pd.notna(row.get("number_required")) else 0,
                    min_cgpa        = float(row.get("min_cgpa", 0)) if pd.notna(row.get("min_cgpa")) else 0,
                    domain_required = str(row.get("domain_required", "")),
                    description     = str(row.get("description", "")),
                    mode            = str(row.get("mode", "")),
                    location        = str(row.get("location", "")),
                    end_date        = str(row.get("end_date", "")),
                    created_at      = str(row.get("created_at", "")),
                ))
                migrated += 1
        db.session.commit()
        print(f"  [Drives]      {migrated} migrated ({len(df)} total)")

    # ── 4. Active Students ────────────────────────────────────────────────────
    def _row_to_student(row, is_active=True, deleted_at=None, deleted_by=None):
        def s(col): return str(row.get(col, "")) if pd.notna(row.get(col, None)) else None
        def f(col): return float(row[col]) if col in row and pd.notna(row[col]) else None
        def i(col): return int(row[col]) if col in row and pd.notna(row[col]) else 0

        return Student(
            batch=s("Batch"), department=s("Department"), student_id=s("Student_ID"),
            register_number=s("Register_Number"), student_name=s("Student_Name"),
            gender=s("Gender"), current_sem=i("Current_Sem"),
            foreign_language_known=s("Foreign_Language_Known"), password=s("Password"),
            cgpa=f("CGPA"),
            sem1_gpa=f("Sem1_GPA"), sem2_gpa=f("Sem2_GPA"), sem3_gpa=f("Sem3_GPA"),
            sem4_gpa=f("Sem4_GPA"), sem5_gpa=f("Sem5_GPA"), sem6_gpa=f("Sem6_GPA"),
            sem7_gpa=f("Sem7_GPA"), sem8_gpa=f("Sem8_GPA"),
            sem1_subjects=s("Sem1_Subjects"), sem1_ia1=s("Sem1_IA1"), sem1_ia2=s("Sem1_IA2"),
            sem1_model=s("Sem1_Model"), sem1_grades=s("Sem1_Grades"),
            sem2_subjects=s("Sem2_Subjects"), sem2_ia1=s("Sem2_IA1"), sem2_ia2=s("Sem2_IA2"),
            sem2_model=s("Sem2_Model"), sem2_grades=s("Sem2_Grades"),
            sem3_subjects=s("Sem3_Subjects"), sem3_ia1=s("Sem3_IA1"), sem3_ia2=s("Sem3_IA2"),
            sem3_model=s("Sem3_Model"), sem3_grades=s("Sem3_Grades"),
            sem4_subjects=s("Sem4_Subjects"), sem4_ia1=s("Sem4_IA1"), sem4_ia2=s("Sem4_IA2"),
            sem4_model=s("Sem4_Model"), sem4_grades=s("Sem4_Grades"),
            sem5_subjects=s("Sem5_Subjects"), sem5_ia1=s("Sem5_IA1"), sem5_ia2=s("Sem5_IA2"),
            sem5_model=s("Sem5_Model"), sem5_grades=s("Sem5_Grades"),
            sem6_subjects=s("Sem6_Subjects"), sem6_ia1=s("Sem6_IA1"), sem6_ia2=s("Sem6_IA2"),
            sem6_model=s("Sem6_Model"), sem6_grades=s("Sem6_Grades"),
            sem7_subjects=s("Sem7_Subjects"), sem7_ia1=s("Sem7_IA1"), sem7_ia2=s("Sem7_IA2"),
            sem7_model=s("Sem7_Model"), sem7_grades=s("Sem7_Grades"),
            sem8_subjects=s("Sem8_Subjects"), sem8_ia1=s("Sem8_IA1"), sem8_ia2=s("Sem8_IA2"),
            sem8_model=s("Sem8_Model"), sem8_grades=s("Sem8_Grades"),
            projects_done=i("Projects_Done"), research_papers_published=i("Research_Papers_Published"),
            review_papers_published=i("Review_Papers_Published"), patents_granted=i("Patents_Granted"),
            hackathons_participated=i("Hackathons_Participated"), hackathons_won_top100=i("Hackathons_Won_Top100"),
            weekly_aptitude_avg=f("Weekly_Aptitude_Avg") or 0,
            avg_communication_score=f("Avg_Communication_Score") or 0,
            number_of_certifications=i("Number_of_Certifications"),
            leetcode_problems_solved=i("LeetCode_Problems_Solved"),
            codechef_rating=i("CodeChef_Rating"),
            certifications_list=s("Certifications_List"),
            certifications_list_with_date=s("Certifications_List_With_Date"),
            certificate_course_level=s("Certificate_Course_Level"),
            certificate_platform=s("Certificate_Platform"),
            certificate_domain=s("Certificate_Domain"),
            certificate_completion_year=s("Certificate_Completion_Year"),
            skill_index=f("skill_index") or 0,
            skill_level=s("skill_level"),
            is_active=is_active,
            deleted_at=deleted_at,
            deleted_by=deleted_by,
        )

    if os.path.exists(MASTER_CSV):
        df = pd.read_csv(MASTER_CSV, dtype=str)
        migrated = 0
        for _, row in df.iterrows():
            reg = str(row.get("Register_Number", "")).strip()
            if reg and not Student.query.filter_by(register_number=reg).first():
                db.session.add(_row_to_student(row, is_active=True))
                migrated += 1
        db.session.commit()
        print(f"  [Students]    {migrated} migrated ({len(df)} total)")

    # ── 5. Recycle Bin (soft-deleted students) ────────────────────────────────
    if os.path.exists(RECYCLE_CSV):
        df = pd.read_csv(RECYCLE_CSV, dtype=str)
        migrated = 0
        for _, row in df.iterrows():
            reg = str(row.get("Register_Number", "")).strip()
            if reg and not Student.query.filter_by(register_number=reg).first():
                del_at = None
                del_at_str = str(row.get("deleted_at", ""))
                try:
                    del_at = datetime.fromisoformat(del_at_str) if del_at_str and del_at_str != "nan" else None
                except Exception:
                    del_at = None
                db.session.add(_row_to_student(row, is_active=False,
                                                deleted_at=del_at,
                                                deleted_by=str(row.get("deleted_by", ""))))
                migrated += 1
        db.session.commit()
        print(f"  [Recycle Bin] {migrated} migrated ({len(df)} total)")

    # ── 6. Certificates ───────────────────────────────────────────────────────
    if os.path.exists(CERT_CSV):
        df = pd.read_csv(CERT_CSV, dtype=str)
        migrated = 0
        for _, row in df.iterrows():
            cid = str(row.get("certificate_id", "")).strip()
            if cid and not Certificate.query.filter_by(certificate_id=cid).first():
                db.session.add(Certificate(
                    certificate_id   = cid,
                    register_number  = str(row.get("register_number", "")),
                    student_name     = str(row.get("student_name", "")),
                    certificate_name = str(row.get("certificate_name", "")),
                    file_path        = str(row.get("file_path", "")),
                    status           = str(row.get("status", "Pending")),
                    uploaded_at      = str(row.get("uploaded_at", "")),
                    reviewed_by      = str(row.get("reviewed_by", "")),
                    reviewed_at      = str(row.get("reviewed_at", "")),
                    remarks          = str(row.get("remarks", "")),
                ))
                migrated += 1
        db.session.commit()
        print(f"  [Certificates]{migrated} migrated ({len(df)} total)")

    # ── 7. Test Results ───────────────────────────────────────────────────────
    if os.path.exists(RESULTS_CSV):
        df = pd.read_csv(RESULTS_CSV, dtype=str)
        migrated = 0
        for _, row in df.iterrows():
            def sv(col): return str(row.get(col, "")) if pd.notna(row.get(col)) else None
            def fv(col): v = row.get(col); return float(v) if pd.notna(v) else 0
            def iv(col): v = row.get(col); return int(float(v)) if pd.notna(v) else 0

            # Duplicate check: same reg + drive_index + round
            exists = TestResult.query.filter_by(
                register_number=sv("register_number"),
                drive_index=iv("drive_index"),
                round=sv("round")
            ).first()
            if not exists:
                db.session.add(TestResult(
                    register_number = sv("register_number"),
                    drive_index     = iv("drive_index"),
                    round           = sv("round"),
                    score           = fv("score"),
                    total           = iv("total"),
                    attempted       = iv("attempted"),
                    correct         = iv("correct"),
                    wrong           = iv("wrong"),
                    marks_correct   = fv("marks_correct"),
                    marks_wrong     = fv("marks_wrong"),
                    cheated         = iv("cheated"),
                    submitted_at    = sv("submitted_at"),
                ))
                migrated += 1
        db.session.commit()
        print(f"  [TestResults] {migrated} migrated ({len(df)} total)")

    print("\n✅ Migration complete. Database: data/portal.db")


if __name__ == "__main__":
    # Allow running standalone: python db_init.py
    from app_new import app
    from models import db
    with app.app_context():
        print("\n🔄 Starting CSV → SQLite migration...\n")
        run_migration(app, db)
