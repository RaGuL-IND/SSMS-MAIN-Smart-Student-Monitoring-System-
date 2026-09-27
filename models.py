# =============================================================================
# models.py — SQLAlchemy ORM Models
# Replaces: master_students.csv, recycle_bin.csv, certificates.csv,
#            company_drives.csv, company_hr.json, test_results.csv, admins.json
# =============================================================================

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# ─────────────────────────────────────────────────────────────────────────────
# Admin
# Replaces: data/admins.json  {username: password_hash}
# ─────────────────────────────────────────────────────────────────────────────
class Admin(db.Model):
    __tablename__ = "admins"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Student
# Replaces: data/master_students.csv  AND  data/recycle_bin.csv
#
# Semester data (subjects, marks, grades) is stored as comma-separated text,
# matching the existing CSV format so that all existing Pandas code works.
# Soft-delete: is_active=False instead of moving rows to recycle_bin.csv
# ─────────────────────────────────────────────────────────────────────────────
class Student(db.Model):
    __tablename__ = "students"

    id                          = db.Column(db.Integer, primary_key=True)

    # Identity
    batch                       = db.Column(db.String(20))
    department                  = db.Column(db.String(100))
    student_id                  = db.Column(db.String(50))
    register_number             = db.Column(db.String(50), unique=True, nullable=False, index=True)
    student_name                = db.Column(db.String(200))
    gender                      = db.Column(db.String(20))
    current_sem                 = db.Column(db.Integer)
    foreign_language_known      = db.Column(db.String(100))
    password                    = db.Column(db.Text)

    # Academic Performance
    cgpa                        = db.Column(db.Float)

    # Semester GPA
    sem1_gpa                    = db.Column(db.Float)
    sem2_gpa                    = db.Column(db.Float)
    sem3_gpa                    = db.Column(db.Float)
    sem4_gpa                    = db.Column(db.Float)
    sem5_gpa                    = db.Column(db.Float)
    sem6_gpa                    = db.Column(db.Float)
    sem7_gpa                    = db.Column(db.Float)
    sem8_gpa                    = db.Column(db.Float)

    # Semester Detail (comma-separated lists, mirrors CSV format)
    sem1_subjects               = db.Column(db.Text)
    sem1_ia1                    = db.Column(db.Text)
    sem1_ia2                    = db.Column(db.Text)
    sem1_model                  = db.Column(db.Text)
    sem1_grades                 = db.Column(db.Text)

    sem2_subjects               = db.Column(db.Text)
    sem2_ia1                    = db.Column(db.Text)
    sem2_ia2                    = db.Column(db.Text)
    sem2_model                  = db.Column(db.Text)
    sem2_grades                 = db.Column(db.Text)

    sem3_subjects               = db.Column(db.Text)
    sem3_ia1                    = db.Column(db.Text)
    sem3_ia2                    = db.Column(db.Text)
    sem3_model                  = db.Column(db.Text)
    sem3_grades                 = db.Column(db.Text)

    sem4_subjects               = db.Column(db.Text)
    sem4_ia1                    = db.Column(db.Text)
    sem4_ia2                    = db.Column(db.Text)
    sem4_model                  = db.Column(db.Text)
    sem4_grades                 = db.Column(db.Text)

    sem5_subjects               = db.Column(db.Text)
    sem5_ia1                    = db.Column(db.Text)
    sem5_ia2                    = db.Column(db.Text)
    sem5_model                  = db.Column(db.Text)
    sem5_grades                 = db.Column(db.Text)

    sem6_subjects               = db.Column(db.Text)
    sem6_ia1                    = db.Column(db.Text)
    sem6_ia2                    = db.Column(db.Text)
    sem6_model                  = db.Column(db.Text)
    sem6_grades                 = db.Column(db.Text)

    sem7_subjects               = db.Column(db.Text)
    sem7_ia1                    = db.Column(db.Text)
    sem7_ia2                    = db.Column(db.Text)
    sem7_model                  = db.Column(db.Text)
    sem7_grades                 = db.Column(db.Text)

    sem8_subjects               = db.Column(db.Text)
    sem8_ia1                    = db.Column(db.Text)
    sem8_ia2                    = db.Column(db.Text)
    sem8_model                  = db.Column(db.Text)
    sem8_grades                 = db.Column(db.Text)

    # Achievements
    projects_done               = db.Column(db.Integer, default=0)
    research_papers_published   = db.Column(db.Integer, default=0)
    review_papers_published     = db.Column(db.Integer, default=0)
    patents_granted             = db.Column(db.Integer, default=0)
    hackathons_participated     = db.Column(db.Integer, default=0)
    hackathons_won_top100       = db.Column(db.Integer, default=0)
    weekly_aptitude_avg         = db.Column(db.Float, default=0)
    avg_communication_score     = db.Column(db.Float, default=0)
    number_of_certifications    = db.Column(db.Integer, default=0)
    leetcode_problems_solved    = db.Column(db.Integer, default=0)
    codechef_rating             = db.Column(db.Integer, default=0)
    certifications_list         = db.Column(db.Text)
    certifications_list_with_date = db.Column(db.Text)

    # Certificate course metadata
    certificate_course_level    = db.Column(db.Text)
    certificate_platform        = db.Column(db.Text)
    certificate_domain          = db.Column(db.Text)
    certificate_completion_year = db.Column(db.Text)

    # ML Score
    skill_index                 = db.Column(db.Float, default=0)
    skill_level                 = db.Column(db.String(50))

    # Soft Delete (replaces recycle_bin.csv)
    is_active                   = db.Column(db.Boolean, default=True, nullable=False, index=True)
    deleted_at                  = db.Column(db.DateTime, nullable=True)
    deleted_by                  = db.Column(db.String(100), nullable=True)

    # Relationships
    certificates  = db.relationship("Certificate", backref="student", lazy=True,
                                    foreign_keys="Certificate.register_number",
                                    primaryjoin="Student.register_number == Certificate.register_number",
                                    cascade="all, delete-orphan")
    test_results  = db.relationship("TestResult", backref="student", lazy=True,
                                    foreign_keys="TestResult.register_number",
                                    primaryjoin="Student.register_number == TestResult.register_number",
                                    cascade="all, delete-orphan")

    def to_dict(self):
        """Return a flat dict matching the CSV column names used by Pandas code."""
        return {
            "Batch":                          self.batch,
            "Department":                     self.department,
            "Student_ID":                     self.student_id,
            "Register_Number":                self.register_number,
            "Student_Name":                   self.student_name,
            "Gender":                         self.gender,
            "Current_Sem":                    self.current_sem,
            "Foreign_Language_Known":         self.foreign_language_known,
            "Password":                       self.password,
            "CGPA":                           self.cgpa,
            "Sem1_GPA": self.sem1_gpa, "Sem2_GPA": self.sem2_gpa,
            "Sem3_GPA": self.sem3_gpa, "Sem4_GPA": self.sem4_gpa,
            "Sem5_GPA": self.sem5_gpa, "Sem6_GPA": self.sem6_gpa,
            "Sem7_GPA": self.sem7_gpa, "Sem8_GPA": self.sem8_gpa,
            "Sem1_Subjects": self.sem1_subjects, "Sem1_IA1": self.sem1_ia1,
            "Sem1_IA2": self.sem1_ia2, "Sem1_Model": self.sem1_model, "Sem1_Grades": self.sem1_grades,
            "Sem2_Subjects": self.sem2_subjects, "Sem2_IA1": self.sem2_ia1,
            "Sem2_IA2": self.sem2_ia2, "Sem2_Model": self.sem2_model, "Sem2_Grades": self.sem2_grades,
            "Sem3_Subjects": self.sem3_subjects, "Sem3_IA1": self.sem3_ia1,
            "Sem3_IA2": self.sem3_ia2, "Sem3_Model": self.sem3_model, "Sem3_Grades": self.sem3_grades,
            "Sem4_Subjects": self.sem4_subjects, "Sem4_IA1": self.sem4_ia1,
            "Sem4_IA2": self.sem4_ia2, "Sem4_Model": self.sem4_model, "Sem4_Grades": self.sem4_grades,
            "Sem5_Subjects": self.sem5_subjects, "Sem5_IA1": self.sem5_ia1,
            "Sem5_IA2": self.sem5_ia2, "Sem5_Model": self.sem5_model, "Sem5_Grades": self.sem5_grades,
            "Sem6_Subjects": self.sem6_subjects, "Sem6_IA1": self.sem6_ia1,
            "Sem6_IA2": self.sem6_ia2, "Sem6_Model": self.sem6_model, "Sem6_Grades": self.sem6_grades,
            "Sem7_Subjects": self.sem7_subjects, "Sem7_IA1": self.sem7_ia1,
            "Sem7_IA2": self.sem7_ia2, "Sem7_Model": self.sem7_model, "Sem7_Grades": self.sem7_grades,
            "Sem8_Subjects": self.sem8_subjects, "Sem8_IA1": self.sem8_ia1,
            "Sem8_IA2": self.sem8_ia2, "Sem8_Model": self.sem8_model, "Sem8_Grades": self.sem8_grades,
            "Projects_Done":                  self.projects_done,
            "Research_Papers_Published":      self.research_papers_published,
            "Review_Papers_Published":        self.review_papers_published,
            "Patents_Granted":                self.patents_granted,
            "Hackathons_Participated":        self.hackathons_participated,
            "Hackathons_Won_Top100":          self.hackathons_won_top100,
            "Weekly_Aptitude_Avg":            self.weekly_aptitude_avg,
            "Avg_Communication_Score":        self.avg_communication_score,
            "Number_of_Certifications":       self.number_of_certifications,
            "LeetCode_Problems_Solved":       self.leetcode_problems_solved,
            "CodeChef_Rating":                self.codechef_rating,
            "Certifications_List":            self.certifications_list,
            "Certifications_List_With_Date":  self.certifications_list_with_date,
            "Certificate_Course_Level":       self.certificate_course_level,
            "Certificate_Platform":           self.certificate_platform,
            "Certificate_Domain":             self.certificate_domain,
            "Certificate_Completion_Year":    self.certificate_completion_year,
            "skill_index":                    self.skill_index,
            "skill_level":                    self.skill_level,
            # Soft-delete columns (for recycle bin compatibility)
            "deleted_at":                     self.deleted_at.isoformat() if self.deleted_at else None,
            "deleted_by":                     self.deleted_by,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Certificate
# Replaces: data/certificates.csv
# ─────────────────────────────────────────────────────────────────────────────
class Certificate(db.Model):
    __tablename__ = "certificates"

    id              = db.Column(db.Integer, primary_key=True)
    certificate_id  = db.Column(db.String(50), unique=True, nullable=False)
    register_number = db.Column(db.String(50), db.ForeignKey("students.register_number", ondelete="CASCADE"),
                                nullable=False, index=True)
    student_name    = db.Column(db.String(200))
    certificate_name= db.Column(db.String(300))
    file_path       = db.Column(db.Text)
    status          = db.Column(db.String(50), default="Pending")
    uploaded_at     = db.Column(db.String(50))
    reviewed_by     = db.Column(db.String(100))
    reviewed_at     = db.Column(db.String(50))
    remarks         = db.Column(db.Text)


# ─────────────────────────────────────────────────────────────────────────────
# CompanyHR
# Replaces: data/company_hr.json
# ─────────────────────────────────────────────────────────────────────────────
class CompanyHR(db.Model):
    __tablename__ = "company_hr"

    id            = db.Column(db.Integer, primary_key=True)
    company_name  = db.Column(db.String(200))
    hr_name       = db.Column(db.String(200))
    email         = db.Column(db.String(200), unique=True, nullable=False, index=True)
    phone         = db.Column(db.String(30))
    position      = db.Column(db.String(200))
    password_hash = db.Column(db.Text)

    drives = db.relationship("Drive", backref="hr", lazy=True,
                             foreign_keys="Drive.hr_email",
                             primaryjoin="CompanyHR.email == Drive.hr_email")


# ─────────────────────────────────────────────────────────────────────────────
# Drive
# Replaces: data/company_drives.csv
# ─────────────────────────────────────────────────────────────────────────────
class Drive(db.Model):
    __tablename__ = "drives"

    id              = db.Column(db.Integer, primary_key=True)
    drive_id        = db.Column(db.String(50), unique=True)
    hr_email        = db.Column(db.String(200), db.ForeignKey("company_hr.email"), index=True)
    company_name    = db.Column(db.String(200))
    position        = db.Column(db.String(200))
    package         = db.Column(db.String(100))
    time_period     = db.Column(db.String(100))
    number_required = db.Column(db.Integer)
    min_cgpa        = db.Column(db.Float)
    domain_required = db.Column(db.String(300))
    description     = db.Column(db.Text)
    mode            = db.Column(db.String(50))
    location        = db.Column(db.String(200))
    end_date        = db.Column(db.String(50))
    created_at      = db.Column(db.String(50))

    # Test assignment (if a test CSV is attached to this drive)
    test_file       = db.Column(db.Text)
    rounds          = db.Column(db.Text)           # JSON list of round names


# ─────────────────────────────────────────────────────────────────────────────
# TestResult
# Replaces: data/test_results.csv
# ─────────────────────────────────────────────────────────────────────────────
class TestResult(db.Model):
    __tablename__ = "test_results"

    id              = db.Column(db.Integer, primary_key=True)
    register_number = db.Column(db.String(50), db.ForeignKey("students.register_number", ondelete="CASCADE"),
                                nullable=False, index=True)
    drive_index     = db.Column(db.Integer, index=True)
    round           = db.Column(db.String(100))
    score           = db.Column(db.Float)
    total           = db.Column(db.Integer)
    attempted       = db.Column(db.Integer)
    correct         = db.Column(db.Integer)
    wrong           = db.Column(db.Integer)
    marks_correct   = db.Column(db.Float)
    marks_wrong     = db.Column(db.Float)
    cheated         = db.Column(db.Integer, default=0)
    submitted_at    = db.Column(db.String(50))
