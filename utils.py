import os
import json
import pandas as pd
import joblib
import sys
import ast
from werkzeug.security import generate_password_hash, check_password_hash
from io import StringIO

# ==========================================================
# PATHS
# ==========================================================
DATA_DIR  = "data"
MODEL_DIR = "model"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# Legacy CSV paths — kept as fallback during transition
MASTER_CSV  = os.path.join(DATA_DIR, "master_students.csv")
RECYCLE_CSV = os.path.join(DATA_DIR, "recycle_bin.csv")
ADMINS_JSON = os.path.join(DATA_DIR, "admins.json")

# ==========================================================
# LOAD ML MODEL
# ==========================================================
def resource_path(relative_path):
    """Make paths work inside PyInstaller EXE."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Use EXE-safe paths
# ==========================================================
# LOAD NEW ML MODEL
# ==========================================================

MODEL_PATH = resource_path("model/best_model.pkl")
ENCODER_PATH = resource_path("model/label_encoder.pkl")

MODEL = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
ENCODER = joblib.load(ENCODER_PATH) if os.path.exists(ENCODER_PATH) else None


# ==========================================================
# ADMIN MANAGEMENT  — backed by SQLite via SQLAlchemy
# Falls back to admins.json if DB is not yet initialised
# ==========================================================
def _db_available():
    """Return True only when a Flask app context with SQLAlchemy is active."""
    try:
        from models import Admin, db
        db.session.execute(db.select(Admin).limit(1))
        return True
    except Exception:
        return False


def read_admins():
    """Return {username: password_hash} dict from DB (or JSON fallback)."""
    if _db_available():
        from models import Admin
        return {a.username: a.password_hash for a in Admin.query.all()}
    # Fallback: JSON file
    if not os.path.exists(ADMINS_JSON):
        return {}
    with open(ADMINS_JSON, "r") as f:
        return json.load(f)


def save_admins(admins):
    """Persist {username: password_hash} dict back to DB (and JSON mirror)."""
    if _db_available():
        from models import Admin, db
        for username, pwd_hash in admins.items():
            existing = Admin.query.filter_by(username=username).first()
            if existing:
                existing.password_hash = pwd_hash
            else:
                db.session.add(Admin(username=username, password_hash=pwd_hash))
        db.session.commit()
    # Always mirror to JSON for backward compatibility
    with open(ADMINS_JSON, "w") as f:
        json.dump(admins, f, indent=2)


def create_admin(username, password):
    admins = read_admins()
    if username in admins:
        raise ValueError("Admin already exists")
    admins[username] = generate_password_hash(password)
    save_admins(admins)


def verify_admin(username, password):
    admins = read_admins()
    return username in admins and check_password_hash(admins[username], password)


# ==========================================================
# STUDENT DATA — backed by SQLite via SQLAlchemy
# Falls back to CSV files if DB is not yet initialised
# ==========================================================

def _students_to_df(students):
    """Convert a list of Student model objects → Pandas DataFrame."""
    if not students:
        return pd.DataFrame()
    return pd.DataFrame([s.to_dict() for s in students])


def _df_row_to_student_obj(row, existing=None):
    """Map a DataFrame row (dict) back to a Student model object."""
    from models import Student
    s = existing or Student()

    def g(col, default=None):
        v = row.get(col, default)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return v

    s.batch                        = g("Batch")
    s.department                   = g("Department")
    s.student_id                   = g("Student_ID")
    s.register_number              = g("Register_Number")
    s.student_name                 = g("Student_Name")
    s.gender                       = g("Gender")
    s.current_sem                  = g("Current_Sem")
    s.foreign_language_known       = g("Foreign_Language_Known")
    s.password                     = g("Password")
    s.cgpa                         = g("CGPA")
    for n in range(1, 9):
        setattr(s, f"sem{n}_gpa",      g(f"Sem{n}_GPA"))
        setattr(s, f"sem{n}_subjects", g(f"Sem{n}_Subjects"))
        setattr(s, f"sem{n}_ia1",      g(f"Sem{n}_IA1"))
        setattr(s, f"sem{n}_ia2",      g(f"Sem{n}_IA2"))
        setattr(s, f"sem{n}_model",    g(f"Sem{n}_Model"))
        setattr(s, f"sem{n}_grades",   g(f"Sem{n}_Grades"))
    s.projects_done                = g("Projects_Done", 0)
    s.research_papers_published    = g("Research_Papers_Published", 0)
    s.review_papers_published      = g("Review_Papers_Published", 0)
    s.patents_granted              = g("Patents_Granted", 0)
    s.hackathons_participated      = g("Hackathons_Participated", 0)
    s.hackathons_won_top100        = g("Hackathons_Won_Top100", 0)
    s.weekly_aptitude_avg          = g("Weekly_Aptitude_Avg", 0)
    s.avg_communication_score      = g("Avg_Communication_Score", 0)
    s.number_of_certifications     = g("Number_of_Certifications", 0)
    s.leetcode_problems_solved     = g("LeetCode_Problems_Solved", 0)
    s.codechef_rating              = g("CodeChef_Rating", 0)
    s.certifications_list          = g("Certifications_List")
    s.certifications_list_with_date= g("Certifications_List_With_Date")
    s.certificate_course_level     = g("Certificate_Course_Level")
    s.certificate_platform         = g("Certificate_Platform")
    s.certificate_domain           = g("Certificate_Domain")
    s.certificate_completion_year  = g("Certificate_Completion_Year")
    s.skill_index                  = g("skill_index", 0)
    s.skill_level                  = g("skill_level")
    return s


def read_master_df():
    """Return all ACTIVE students as a Pandas DataFrame."""
    if _db_available():
        from models import Student
        return _students_to_df(Student.query.filter_by(is_active=True).all())
    # Fallback: CSV
    if not os.path.exists(MASTER_CSV):
        return pd.DataFrame()
    return pd.read_csv(MASTER_CSV)


def save_master_df(df):
    """Upsert every row from df back into the students table."""
    if _db_available():
        from models import Student, db
        for _, row in df.iterrows():
            reg = str(row.get("Register_Number", "")).strip()
            if not reg:
                continue
            existing = Student.query.filter_by(register_number=reg).first()
            obj = _df_row_to_student_obj(row.to_dict(), existing=existing)
            obj.is_active = True
            if not existing:
                db.session.add(obj)
        db.session.commit()
    # Mirror to CSV for backward-compatibility with legacy scripts
    df.to_csv(MASTER_CSV, index=False)


def read_recycle_df():
    """Return all SOFT-DELETED students as a Pandas DataFrame."""
    if _db_available():
        from models import Student
        return _students_to_df(Student.query.filter_by(is_active=False).all())
    # Fallback: CSV
    if not os.path.exists(RECYCLE_CSV):
        return pd.DataFrame()
    return pd.read_csv(RECYCLE_CSV)


def save_recycle_df(df):
    """Mark students in df as soft-deleted (is_active=False)."""
    if _db_available():
        from models import Student, db
        from datetime import datetime
        for _, row in df.iterrows():
            reg = str(row.get("Register_Number", "")).strip()
            if not reg:
                continue
            s = Student.query.filter_by(register_number=reg).first()
            if s:
                s.is_active  = False
                s.deleted_at = s.deleted_at or datetime.utcnow()
                s.deleted_by = str(row.get("deleted_by", ""))
        db.session.commit()
    # Mirror to CSV
    df.to_csv(RECYCLE_CSV, index=False)



# ==========================================================
# SKILL INDEX CALCULATION
# ==========================================================
def compute_skill_index_for_row(row):

    try:

        # -----------------------------
        # Academic Score
        # -----------------------------
        cgpa = float(row.get("CGPA", 0))

        projects = float(row.get("Projects_Done", 0))
        papers = float(row.get("Research_Papers_Published", 0))
        hackathons = float(row.get("Hackathons_Participated", 0))

        academic_score = (
            cgpa * 10 +
            projects * 4 +
            papers * 8 +
            hackathons * 5
        )

        # -----------------------------
        # Certificate Score
        # -----------------------------
        levels = str(row.get("Certificate_Course_Level", "")).split(",")
        platforms = str(row.get("Certificate_Platform", "")).split(",")
        domains = str(row.get("Certificate_Domain", "")).split(",")
        years = str(row.get("Certificate_Completion_Year", "")).split(",")

        level_weight = {
            "Beginner": 5,
            "Intermediate": 10,
            "Advanced": 15,
            "Professional": 20
        }

        platform_weight = {
            "Coursera": 1.4,
            "Google": 1.4,
            "Microsoft": 1.4,
            "Cisco": 1.5,
            "NPTEL": 1.5,
            "Udemy": 1.2
        }

        domain_weight = {
            "AI": 1.5,
            "Data Science": 1.4,
            "Cybersecurity": 1.4,
            "Cloud Computing": 1.3,
            "Programming": 1.2,
            "Networking": 1.2
        }

        cert_score = 0

        for i in range(len(levels)):

            level = levels[i].strip()
            platform = platforms[i].strip() if i < len(platforms) else ""
            domain = domains[i].strip() if i < len(domains) else ""

            base = level_weight.get(level, 5)
            p_weight = platform_weight.get(platform, 1.0)
            d_weight = domain_weight.get(domain, 1.0)

            cert_score += base * p_weight * d_weight

        # -----------------------------
        # Final Skill Index
        # -----------------------------
        feature_df = pd.DataFrame([[
            academic_score,
            cert_score,
            float(row.get("Number_of_Certifications", 0)),
            float(row.get("Hackathons_Participated", 0))
        ]], columns=[
            "academic_score",
            "certificate_score",
            "certificate_count",
            "hackathons"
        ])

        # Try ML model first; on ANY error fall back to the weighted formula
        if MODEL is not None:
            try:
                proba = MODEL.predict_proba(feature_df)[0]
                score = (
                    proba[1] * 40 +
                    proba[2] * 70 +
                    proba[3] * 90
                )
                return round(score, 2)
            except Exception as model_err:
                print("ML model prediction failed, using fallback formula:", model_err)

        # Weighted fallback formula (capped at 100)
        return round(min((0.5 * academic_score) + (0.5 * cert_score), 100), 2)

    except Exception as e:
        print("Skill index error:", e)
        return 0

    
def parse_list_field(val):
    """
    Safely parse a sem subjects/IA1/IA2/model list field.
    Supports:
      - Python lists: ['A','B']
      - JSON lists: ["A","B"]
      - CSV lists: A,B,C
      - Pipe lists: A|B|C
      - Broken formats: ['A', "B"] etc.
    """
    if pd.isna(val) or val == "":
        return []

    if isinstance(val, (list, tuple)):
        return list(val)

    s = str(val).strip()

    # Try Python literal list → ['A','B']
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed]
    except Exception:
        pass

    # Try JSON list → ["A","B"]
    try:
        parsed = json.loads(s.replace("'", '"'))
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed]
    except Exception:
        pass

    # Fallback parsing
    if "," in s:
        return [x.strip() for x in s.split(",") if x.strip()]

    if "|" in s:
        return [x.strip() for x in s.split("|") if x.strip()]

    # Single item fallback
    return [s]
def compute_analysis_from_df(df, selected_sem=None):
    """
    Compute numeric summary, language distribution, subject-level raw & normalized scores.
    All returned values are JSON-safe (int, float, str).
    """
    out = {}
    source_semester_map = {}

    # ----- NUMERIC SUMMARY -----
    numeric_cols = [
        c for c in df.columns
        if c.lower() in ("cgpa", "weekly_aptitude_avg", "avg_communication_score")
        or df[c].dtype.kind in "biuf"
    ]

    summary = {}
    for col in numeric_cols:
        try:
            ser = pd.to_numeric(df[col], errors="coerce").dropna()
            summary[col] = {
                "count": int(ser.count()),
                "mean": float(round(ser.mean(), 2)) if not ser.empty else None,
                "min": float(round(ser.min(), 2)) if not ser.empty else None,
                "max": float(round(ser.max(), 2)) if not ser.empty else None
            }
        except:
            summary[col] = {"count": 0, "mean": None, "min": None, "max": None}

    out["summary_numeric"] = summary

    # ----- LANGUAGE DISTRIBUTION -----
    if "Foreign_Language_Known" in df.columns:
        langs = df["Foreign_Language_Known"].fillna("").astype(str)
        dist = {str(k): int(v) for k, v in langs.value_counts().to_dict().items()}

        lang_students = {}
        for lang in dist:
            if lang.strip() == "":
                continue
            sub = df[langs == lang]
            lang_students[lang] = [
            {
                k: ("" if pd.isna(v) else v)
                for k, v in r.to_dict().items()
            }
            for _, r in sub.iterrows()
            ]

        out["foreign_language_dist"] = dist
        out["foreign_language_students"] = lang_students
    else:
        out["foreign_language_dist"] = {}
        out["foreign_language_students"] = {}

    # ----- SUBJECT-PERFORMANCE EXTRACTION -----
    subjects_map = {}

    for sem in range(1, 9):
        subj_col = f"Sem{sem}_Subjects"
        ia1_col = f"Sem{sem}_IA1"
        ia2_col = f"Sem{sem}_IA2"
        model_col = f"Sem{sem}_Model"

        if subj_col not in df.columns:
            continue

        for _, row in df.iterrows():
            subj_list = parse_list_field(row.get(subj_col, ""))
            ia1_list = parse_list_field(row.get(ia1_col, ""))
            ia2_list = parse_list_field(row.get(ia2_col, ""))
            model_list = parse_list_field(row.get(model_col, ""))

            for i, subj in enumerate(subj_list):
                subj_name = str(subj).strip()
                if subj_name == "":
                    continue
                source_semester_map[subj_name] = sem

                def safe(lst):
                    try:
                        return float(lst[i])
                    except:
                        return 0.0

                raw_total = safe(ia1_list) + safe(ia2_list) + safe(model_list)

                subjects_map.setdefault(subj_name, []).append({
                    "student_id": str(row.get("Student_ID", "")),
                    "student_name": str(row.get("Student_Name", "")),
                    "raw_score": float(raw_total),
                    "cgpa": float(row.get("CGPA", 0))
                })

    # ----- SUBJECT SUMMARY -----
    subject_summary = {}

    for subject, recs in subjects_map.items():
        raw_scores = [r["raw_score"] for r in recs]
        max_raw = max(raw_scores) if raw_scores else 1.0
        if max_raw <= 0:
            max_raw = 1.0

        for r in recs:
            r["normalized_score"] = float(round((r["raw_score"] / max_raw) * 100, 2))

        scores = [r["normalized_score"] for r in recs]
        avg = float(round(sum(scores) / len(scores), 2)) if scores else 0.0

        def clean(lst):
            return [
                {
                    "student_id": r["student_id"],
                    "student_name": r["student_name"],
                    "raw_score": float(r["raw_score"]),
                    "normalized_score": float(r["normalized_score"]),
                    "cgpa": float(r["cgpa"])
                }
                for r in lst
            ]

        top5 = clean(sorted(recs, key=lambda x: x["normalized_score"], reverse=True)[:5])
        least5 = clean(sorted(recs, key=lambda x: x["normalized_score"])[:5])

        mn, mx = min(scores), max(scores)

        # Buckets
        if mn == mx:
            buckets = [{
                "label": f"{mn}",
                "min": float(mn),
                "max": float(mx),
                "count": len(scores)
            }]
        else:
            step = (mx - mn) / 5
            buckets = []
            for b in range(5):
                low = mn + b * step
                high = mn + (b + 1) * step if b < 4 else mx
                count = sum(low <= s <= high for s in scores)
                buckets.append({
                    "label": f"{round(low,1)} - {round(high,1)}",
                    "min": float(low),
                    "max": float(high),
                    "count": int(count)
                })

        subject_summary[subject] = {
            "avg": avg,
            "top": top5,
            "least": least5,
            "buckets": buckets,
            "subject_max_raw": float(max_raw)
        }

    # ----- CGPA VS SKILL INDEX CORRELATION SCATTER -----
    scatter_data = []
    if "CGPA" in df.columns and "skill_index" in df.columns:
        for _, row in df.iterrows():
            try:
                cgpa = float(row.get("CGPA", 0))
                skill_idx = float(row.get("skill_index", 0))
                name = str(row.get("Student_Name", "Student"))
                scatter_data.append({"x": cgpa, "y": skill_idx, "label": name})
            except:
                pass
    out["cgpa_skill_correlation"] = scatter_data

    # ----- DEPARTMENT AVERAGE SKILL INDEX -----
    dept_avg_skill = {}
    if "Department" in df.columns and "skill_index" in df.columns:
        try:
            temp_df = df.copy()
            temp_df["skill_index"] = pd.to_numeric(temp_df["skill_index"], errors="coerce")
            temp_df = temp_df.dropna(subset=["skill_index"])
            grouped = temp_df.groupby("Department")["skill_index"].mean().to_dict()
            dept_avg_skill = {str(k): float(round(v, 2)) for k, v in grouped.items()}
        except Exception as e:
            print("Error grouping dept avg skill:", e)
    out["dept_avg_skill"] = dept_avg_skill

    out["subject_summary"] = subject_summary
    out["source_semester_map"] = source_semester_map
    return out

def classify_skill_level(score):

    try:
        score = float(score)
    except:
        return "Unknown"

    if score < 40:
        return "Beginner"
    elif score < 60:
        return "Intermediate"
    elif score < 80:
        return "Advanced"
    else:
        return "Expert"

# ==========================================================
# MERGE CSV INTO MASTER
# ==========================================================
def merge_upload_df(upload_df, admin_user="system"):
    master = read_master_df()

    upload_df["Register_Number"] = upload_df["Register_Number"].astype(str)
    if not master.empty:
        master["Register_Number"] = master["Register_Number"].astype(str)

    if master.empty:
        # first upload → compute skill index for all rows
        upload_df["skill_index"] = upload_df.apply(compute_skill_index_for_row, axis=1)
        save_master_df(upload_df)
        return {"updated": len(upload_df)}

    # update or insert rows
    for _, row in upload_df.iterrows():
        reg = row["Register_Number"]
        exists = master[master["Register_Number"] == reg]

        if not exists.empty:
            idx = exists.index[0]
            for col in upload_df.columns:
                if pd.notna(row[col]) and row[col] != "":
                    master.at[idx, col] = row[col]
        else:
            master = pd.concat([master, pd.DataFrame([row])], ignore_index=True)

    # recompute skill index for all
    master["skill_index"] = master.apply(compute_skill_index_for_row, axis=1)
    master["skill_level"] = master["skill_index"].apply(classify_skill_level)
    save_master_df(master)
    return {"updated": len(upload_df)}


# ==========================================================
# ELIGIBILITY CHECK LOGIC
# ==========================================================

# ==========================================================
# UPDATED ELIGIBILITY LOGIC (IA1/IA2 out of 20, Model out of 100)
# ==========================================================

import ast

# DOMAIN → REQUIRED SUBJECTS
DOMAIN_SUBJECTS = {
    "Machine Learning / AI": [
        "Machine Learning", "Deep Learning", "Neural Networks",
        "Artificial Intelligence", "Statistics", "Probability",
        "Linear Algebra", "Python"
    ],
    "Web Development / Full Stack": [
        "Web Technology", "Internet Programming", "HTML", "CSS",
        "JavaScript", "React", "NodeJS", "DBMS"
    ],
    "Data Science / Analytics": [
        "Statistics", "Data Mining", "Data Science",
        "Python", "R", "Big Data", "Probability"
    ],
    "Cyber Security": [
        "Computer Networks", "Network Security",
        "Cryptography", "Ethical Hacking", "Operating Systems"
    ],
    "Cloud Computing / DevOps": [
        "Cloud Computing", "Distributed Systems", "Operating Systems",
        "Virtualization", "Computer Networks"
    ],
    "Software Development": [
        "Data Structures", "Algorithms", "OOPS",
        "Java", "C++", "Software Engineering"
    ],
    "IoT / Embedded Systems": [
        "IoT", "Embedded Systems", "Microcontrollers",
        "Wireless Sensor Networks"
    ],
    "Robotics / Automation": [
        "Robotics", "Control Systems", "AI", "Image Processing"
    ]
}

# Convert raw marks into percentage
def calc_percentage(ia1, ia2, model):
    ia1_pct = (ia1 / 20) * 100
    ia2_pct = (ia2 / 20) * 100
    model_pct = (model / 100) * 100
    return ia1_pct, ia2_pct, model_pct


# A subject is valid if ANY 2/3 percentages ≥ 70
def subject_pass(ia1, ia2, model):
    ia1_pct, ia2_pct, model_pct = calc_percentage(ia1, ia2, model)
    passed = sum([
        ia1_pct >= 70,
        ia2_pct >= 70,
        model_pct >= 70
    ])
    return passed >= 2   # ANY 2 must be ≥ 70%


# MAIN eligibility function
def is_student_eligible(student, company):
    domain = company["domain_required"]
    min_cgpa = float(company["min_cgpa"])

    # 1) CGPA check
    if float(student["CGPA"]) < min_cgpa:
        return False

    required = DOMAIN_SUBJECTS.get(domain, [])
    if not required:
        return False

    eligible_subjects = 0

    # 2) Check subjects + marks across Sem1–Sem6
    for i in range(1, 7):
        sub_col = f"Sem{i}_Subjects"
        ia1_col = f"Sem{i}_IA1"
        ia2_col = f"Sem{i}_IA2"
        model_col = f"Sem{i}_Model"

        if sub_col not in student:
            continue

        try:
            subjects = ast.literal_eval(student[sub_col])
            ia1_list = ast.literal_eval(student[ia1_col])
            ia2_list = ast.literal_eval(student[ia2_col])
            model_list = ast.literal_eval(student[model_col])
        except:
            continue

        # Check each subject in the semester
        for idx, sub in enumerate(subjects):
            if sub in required:
                ia1 = ia1_list[idx] if idx < len(ia1_list) else 0
                ia2 = ia2_list[idx] if idx < len(ia2_list) else 0
                model = model_list[idx] if idx < len(model_list) else 0

                if subject_pass(ia1, ia2, model):
                    eligible_subjects += 1

    # 3) Apply 30% subject requirement
    subject_ratio = eligible_subjects / len(required)
    return subject_ratio >= 0.30   # UPDATED threshold


# Wrapper: return eligible students list
def get_eligible_students_for_company(company_row):
    master = read_master_df()
    eligible = []

    for _, student in master.iterrows():
        if is_student_eligible(student, company_row):
            eligible.append(student.to_dict())

    return eligible
