from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import pandas as pd
import os
import random
import csv
from datetime import datetime
import math
import ast
from scheme_recommender import ml_recommend_schemes
from werkzeug.utils import secure_filename

# ----------------------------------
# CONFIG
# ----------------------------------

app = Flask(__name__)
app.secret_key = "studentportalkey123"

DATA_DIR = "data"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

CERT_UPLOAD_DIR = os.path.join(DATA_DIR, "certificates")
# ------------------------------
# RESUME STORAGE
# ------------------------------
RESUME_DIR = os.path.join(DATA_DIR, "resumes")
os.makedirs(RESUME_DIR, exist_ok=True)
CERT_CSV = os.path.join(DATA_DIR, "certificates.csv")

MASTER_CSV = os.path.join(DATA_DIR, "master_students.csv")
DATA_PATH = MASTER_CSV
COMPANY_DRIVES = os.path.join(DATA_DIR, "company_drives.csv")

TESTS_DIR = os.path.join(DATA_DIR, "tests")
RESULTS_CSV = os.path.join(DATA_DIR, "test_results.csv")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CERT_UPLOAD_DIR, exist_ok=True)
os.makedirs(TESTS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
os.makedirs(CERT_UPLOAD_DIR, exist_ok=True)

@app.route("/student/upload_certificate", methods=["GET", "POST"])
def upload_certificate():
    if "student_reg_no" not in session:
        return redirect(url_for("login"))

    reg_no = session["student_reg_no"]
    df = load_students()
    student = df[df["Register_Number"] == reg_no].iloc[0]

    if request.method == "POST":
        cert_name = request.form.get("certificate_name", "").strip()
        file = request.files.get("certificate")

        if not cert_name or not file:
            flash("All fields are required")
            return redirect(request.url)

        filename = f"{reg_no}_{int(datetime.now().timestamp())}_{file.filename}"
        save_path = os.path.join(CERT_UPLOAD_DIR, filename)
        file.save(save_path)

        # Load or create CSV
        if os.path.exists(CERT_CSV):
            cert_df = pd.read_csv(CERT_CSV)
        else:
           cert_df = pd.DataFrame(columns=[
    "certificate_id",
    "register_number",
    "student_name",
    "certificate_name",
    "file_path",
    "status",
    "uploaded_at",
    "reviewed_by",
    "reviewed_at",
    "remarks"
])

        cert_df.loc[len(cert_df)] = {
            "certificate_id": len(cert_df) + 1,
            "register_number": reg_no,
            "student_name": student["Student_Name"],
            "certificate_name": cert_name,
            "file_path": filename,

            "status": "pending",
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "reviewed_by": "",
            "reviewed_at": "",
            "remarks": ""
        }

        cert_df.to_csv(CERT_CSV, index=False)
        flash("Certificate submitted for admin approval")
        return redirect(url_for("dashboard"))

    return render_template("student_upload_certificate.html")

# ----------------------------------
# RESUME UPLOAD
# ----------------------------------
@app.route("/student/upload_resume", methods=["GET", "POST"])
def upload_resume():

    if "student_reg_no" not in session:
        return redirect(url_for("login"))

    reg_no = session["student_reg_no"]

    if request.method == "POST":

        file = request.files.get("resume")

        if not file:
            flash("Please select a resume file.")
            return redirect(request.url)

        filename = secure_filename(f"{reg_no}_resume_{file.filename}")
        save_path = os.path.join(RESUME_DIR, filename)

        file.save(save_path)

        flash("Resume uploaded successfully.")
        return redirect(url_for("dashboard"))

    return render_template("student_upload_resume.html")


@app.route("/student/certificates")
def student_certificates():
    if "student_reg_no" not in session:
        return redirect(url_for("login"))

    if not os.path.exists(CERT_CSV):
        return render_template("student_certificates.html", certs=[])

    df = pd.read_csv(CERT_CSV)
    certs = df[
        (df["register_number"] == session["student_reg_no"]) &
        (df["status"] == "approved")
    ]

    return render_template("student_certificates.html", certs=certs.to_dict(orient="records"))
MASTER_CSV = "data/master_students.csv"
app.secret_key = "studentportalkey123"

DATA_PATH = os.path.join("data", "master_students.csv")
COMPANY_DRIVES = os.path.join("data", "company_drives.csv")

TESTS_DIR = "data/tests"
RESULTS_CSV = "data/test_results.csv"

if not os.path.exists(TESTS_DIR):
    os.makedirs(TESTS_DIR)
# ------------------------------
# READ MASTER STUDENT DATA
# ------------------------------
def load_students():
    if not os.path.exists(DATA_PATH):
        return pd.DataFrame()

    df = pd.read_csv(DATA_PATH)

    # Always ensure Register_Number is string
    df["Register_Number"] = df["Register_Number"].astype(str)

    # 🔥 Ensure Password column exists
    if "Password" not in df.columns:
        df["Password"] = "helloeveryone"     # default password for all
        df.to_csv(DATA_PATH, index=False)    # save back to CSV

    return df
   
# ----------------------------------
# CERTIFICATE FILE VIEW (STUDENT + ADMIN)
# ----------------------------------
@app.route("/certificates/view/<path:filename>")
def view_certificate_file(filename):
    file_path = os.path.join(DATA_DIR, "certificates", filename)

    if not os.path.exists(file_path):
        return "File not found", 404

    return send_file(file_path)
def load_company_drives():
    if os.path.exists(COMPANY_DRIVES):
        return pd.read_csv(COMPANY_DRIVES)
    return pd.DataFrame()

# ------------------------------
# LOGIN PAGE
# ------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        reg_no = request.form["register_number"].strip()
        password = request.form["password"].strip()

        df = load_students()

        if df.empty:
            flash("No student records found.")
            return redirect(url_for("login"))

        # Convert to string for safety
        df["Register_Number"] = df["Register_Number"].astype(str).str.strip()
        # Ensure Password column exists
        if "Password" not in df.columns:
            df["Password"] = "helloeveryone"
            df.to_csv(MASTER_CSV, index=False)

        df["Password"] = df["Password"].astype(str).str.strip()
        

        # Find the student
        student = df[df["Register_Number"] == reg_no]

        if student.empty:
            flash("Invalid Register Number.")
            return redirect(url_for("login"))

        stored_password = student.iloc[0]["Password"]

        # ---------------------------
        # 1️⃣ FIRST TIME LOGIN CHECK
        # ---------------------------
        if stored_password == "helloeveryone":
            if password == "helloeveryone":
                session["temp_student"] = reg_no
                return redirect(url_for("create_password"))
            else:
                flash("You must enter the default password 'helloeveryone' for first login.")
                return redirect(url_for("login"))

        # ---------------------------
        # 2️⃣ NORMAL LOGIN
        # ---------------------------
        if password == stored_password:
            session["student_reg_no"] = reg_no
            return redirect(url_for("dashboard"))
        else:
            flash("Incorrect password.")
            return redirect(url_for("login"))

    return render_template("student_login.html")


@app.route("/create_password", methods=["GET", "POST"])
def create_password():
    if "temp_student" not in session:
        return redirect(url_for("login"))

    reg_no = session["temp_student"]

    if request.method == "POST":
        new_password = request.form["new_password"].strip()

        # Load CSV
        df = load_students()

        # Update password
        df.loc[df["Register_Number"].astype(str).str.strip() == reg_no, "Password"] = new_password

        # Save CSV
        df.to_csv(MASTER_CSV, index=False)

        # Move student to full session
        session["student_reg_no"] = reg_no
        session.pop("temp_student", None)

        return redirect(url_for("dashboard"))

    return render_template("create_password.html")




# ------------------------------
# STUDENT DASHBOARD
# ------------------------------
@app.route("/dashboard")
def dashboard():
    if "student_reg_no" not in session:
        return redirect(url_for("login"))

    reg_no = session["student_reg_no"]
    df = load_students()

    student_df = df[df["Register_Number"] == reg_no]
    if student_df.empty:
        flash("Your profile was removed by admin.")
        return redirect(url_for("login"))

    student = student_df.to_dict(orient="records")[0]

    # ----------------------------------
    # FIX: Prepare semester data for Jinja
    # ----------------------------------
    for col in df.columns:
        if col.startswith("Sem") and col.endswith("_GPA"):
            sem = col.split("_")[0]

            for key in ["Subjects", "IA1", "IA2", "Model", "Grades"]:
                full_key = f"{sem}_{key}"
                value = student.get(full_key, "")

                if pd.isna(value) or value == "":
                    student[full_key] = []
                else:
                    student[full_key] = str(value).split(",")

    # ----------------------------------
    # GOVERNMENT SCHEMES
    # ----------------------------------
    schemes_all = ml_recommend_schemes(student)
    eligible_schemes = [s for s in schemes_all if s["probability"] >= 70]

    # ----------------------------------
    # SEMESTER LIST
    # ----------------------------------
    semesters = sorted(
        [c.split("_")[0] for c in df.columns if c.startswith("Sem") and c.endswith("_GPA")],
        key=lambda x: int(x.replace("Sem", ""))
    )

    return render_template(
        "student_dashboard.html",
        student=student,
        semesters=semesters,
        schemes=eligible_schemes
    )
# ------------------------------
# STUDENT DRIVES MENU
# ------------------------------
@app.route("/student/drives")
def student_drives():
    if "student_reg_no" not in session:
        return redirect(url_for("login"))
    return render_template("student_drives.html")
# ------------------------------
# CURRENT DRIVES
# ------------------------------
@app.route("/student/drives/current")
def student_current_drives():
    if "student_reg_no" not in session:
        return redirect(url_for("login"))

    reg_no = session["student_reg_no"]
    df = load_company_drives()

    # Load test results if available
    results_df = pd.read_csv(RESULTS_CSV) if os.path.exists(RESULTS_CSV) else pd.DataFrame()

    # Add test status for each drive
    status_list = []

    for i in range(len(df)):
        row = df.iloc[i].copy()

        # Default: student has not attended anything
        drive_status = "attend"

        if not results_df.empty:
            # get all attempts for this drive by student
            attempts = results_df[
                (results_df["register_number"] == reg_no) &
                (results_df["drive_index"] == i)
            ]

            if not attempts.empty:
                # Check if cheated
                if (attempts["cheated"] == 1).any():
                    drive_status = "cheated"
                else:
                    drive_status = "attended"

        row["test_status"] = drive_status
        status_list.append(row)

    updated_df = pd.DataFrame(status_list)

    return render_template("student_current_drives.html", drives=updated_df)

@app.route("/student/drives/test/<int:index>")
def student_attend_test(index):
    df = load_company_drives()

    if index >= len(df):
        return "Invalid test link", 404

    link = df.iloc[index].get("test_link", "")

    if link == "" or pd.isna(link):
        return "Test not available yet", 404

    return redirect(link)
# ------------------------------
# TEST INSTRUCTIONS PAGE
# ------------------------------
@app.route("/student/test/instructions/<int:drive_index>")
def test_instructions(drive_index):
    df = load_company_drives()
    row = df.iloc[drive_index]

    tests_available = {
        "Aptitude Test": bool(row.get("aptitude_test_link")),
        "Domain Test": bool(row.get("domain_test_link")),
        "Coding Test": bool(row.get("coding_test_link"))
    }

    return render_template(
        "student_test_instructions.html",
        drive=row,
        drive_index=drive_index,
        tests=tests_available
    )
# ------------------------------
# PER-ROUND INSTRUCTIONS PAGE
# ------------------------------
@app.route("/student/test/instructions/<int:drive_index>/<round>")
def round_instructions(drive_index, round):
    df = load_company_drives()
    row = df.iloc[drive_index]

    test_names = {
        "aptitude": "Aptitude Test",
        "domain": "Domain-Based Test",
        "coding": "Coding Test"
    }

    duration = row.get(f"{round}_duration", 30)
    question_count = 60  # You fixed this earlier

    return render_template(
        "student_round_instructions.html",
        drive_index=drive_index,
        round=round,
        round_name=test_names[round],
        duration=duration,
        question_count=question_count
    )

# ------------------------------
# CHECK IF STUDENT ALREADY ATTEMPTED THIS ROUND
# ------------------------------
def has_attempted_test(reg_no, drive_index, round):
    if not os.path.exists(RESULTS_CSV):
        return False

    df = pd.read_csv(RESULTS_CSV)

    match = df[
        (df["register_number"] == reg_no) &
        (df["drive_index"] == drive_index) &
        (df["round"] == round)
    ]

    return not match.empty

# ------------------------------  
# START TEST ROUND  
# ------------------------------  
@app.route("/student/test/start/<int:drive_index>/<round>")
def start_test_round(drive_index, round):
        # BLOCK REATTEMPTS
    reg_no = session.get("student_reg_no")
        # -----------------------------------
    # BLOCK STUDENTS WHO WERE ALREADY CAUGHT CHEATING
    # -----------------------------------
    if os.path.exists(RESULTS_CSV):
        df_results = pd.read_csv(RESULTS_CSV)

    # If cheated column does not exist yet, add it
        if "cheated" not in df_results.columns:
            df_results["cheated"] = 0

        cheated_record = df_results[
        (df_results["register_number"] == reg_no) &
        (df_results["drive_index"] == drive_index) &
        (df_results["cheated"] == 1)
    ]

    


        if not cheated_record.empty:
            return "❌ You are disqualified due to cheating and cannot continue.", 403

    if has_attempted_test(reg_no, drive_index, round):
        return "❌ You have already attempted this test. Reattempt is not allowed.", 403

    df = load_company_drives()
    row = df.iloc[drive_index]

    raw_file = row.get(f"{round}_test_link", "")

    if not isinstance(raw_file, str):
        raw_file = ""

    filename = raw_file.replace("internal:", "").strip()

    if filename == "":
        return "Test file missing or not assigned by admin", 404

    duration = row.get(f"{round}_duration", 30)

    questions = read_test_file(filename)


    return render_template("student_take_test.html",
                           questions=questions,
                           drive_index=drive_index,
                           round=round,
                           duration_minutes=duration)


# ------------------------------  
# READ TEST FILE (random Q + random options)  
# ------------------------------  
def read_test_file(filename, desired_count=60):
    """
    Read a test CSV from data/tests/<filename> and return a list of question dicts.
    This function:
      - Detects 'Category' column (topic)
      - Builds per-topic pools
      - Assigns quotas proportionally to each topic (while ensuring min 1 per topic)
      - Caps quotas to available questions and redistributes leftovers
      - Randomly selects questions per topic and shuffles options & questions
    Returns a list of dicts: {"q": text, "options": [...], "answer_index": int}
    """
    path = os.path.join("data/tests", filename)
    if not os.path.exists(path):
        return []

    df = pd.read_csv(path)

    # Normalize column names (in case of leading/trailing spaces)
    df.columns = [c.strip() for c in df.columns]

    # If there's no Category/Topic column, fallback to random selection
    category_col = None
    for candidate in ("Category", "Topic", "category", "topic"):
        if candidate in df.columns:
            category_col = candidate
            break

    all_questions = []

    # Helper to build question dict with shuffled options and computed answer_index
    def build_question_from_row(r):
        q_text = str(r.get("Question", "")).strip()
        options = [
            str(r.get("OptionA", "")).strip(),
            str(r.get("OptionB", "")).strip(),
            str(r.get("OptionC", "")).strip(),
            str(r.get("OptionD", "")).strip(),
        ]
        correct_ans = str(r.get("Answer", "")).strip()

        # Determine correct option text (handle A/B/C/D or full text)
        correct_index = None
        if correct_ans.upper() in ["A", "B", "C", "D"]:
            try:
                correct_index = ord(correct_ans.upper()) - ord("A")
            except Exception:
                correct_index = None
        if correct_index is None:
            # fallback: match text
            try:
                correct_index = options.index(correct_ans)
            except Exception:
                # if no match, set -1 and later ignore (shouldn't happen)
                correct_index = 0

        correct_text = options[correct_index] if 0 <= correct_index < len(options) else options[0]

        # Shuffle options and compute new index
        shuffled = options.copy()
        random.shuffle(shuffled)
        try:
            new_correct_index = shuffled.index(correct_text)
        except ValueError:
            new_correct_index = 0

        return {"q": q_text, "options": shuffled, "answer_index": new_correct_index}

    # If no category column, just randomly pick 'desired_count' questions
    if category_col is None:
        for _, r in df.iterrows():
            all_questions.append(build_question_from_row(r))

        random.shuffle(all_questions)
        return all_questions[:min(desired_count, len(all_questions))]

    # Build mapping: topic -> list of rows (indices)
    topic_groups = {}
    for idx, r in df.iterrows():
        topic = str(r.get(category_col, "")).strip()
        if topic == "" or topic.lower() == "nan":
            topic = "Unspecified"
        topic_groups.setdefault(topic, []).append(r)

    # Counts
    topic_counts = {t: len(lst) for t, lst in topic_groups.items()}
    total_questions_available = sum(topic_counts.values())
    if total_questions_available == 0:
        return []

    # If desired_count >= available, return all (still shuffle options & questions)
    if desired_count >= total_questions_available:
        for t, rows in topic_groups.items():
            for r in rows:
                all_questions.append(build_question_from_row(r))
        random.shuffle(all_questions)
        return all_questions

    # Compute proportional quotas (using largest fractional remainder method)
    ideal = {}
    for t, cnt in topic_counts.items():
        ideal_val = (cnt / total_questions_available) * desired_count
        ideal[t] = ideal_val

    # initial floor quotas, ensure at least 1 per topic
    quotas = {}
    for t, val in ideal.items():
        q = int(math.floor(val))
        if q < 1:
            q = 1
        # do not exceed available questions
        q = min(q, topic_counts[t])
        quotas[t] = q

    assigned = sum(quotas.values())
    remaining = desired_count - assigned

    # fractional parts for distribution
    frac_parts = []
    for t, val in ideal.items():
        frac = val - math.floor(val)
        frac_parts.append((frac, t))
    frac_parts.sort(reverse=True)  # largest fractional first

    # Distribute remaining slots according to fractional parts, respecting caps
    i = 0
    while remaining > 0 and i < len(frac_parts):
        _, t = frac_parts[i]
        if quotas[t] < topic_counts[t]:
            quotas[t] += 1
            remaining -= 1
        i += 1
        if i == len(frac_parts) and remaining > 0:
            # second pass: give to any with spare capacity
            for t2 in topic_counts:
                if remaining == 0:
                    break
                if quotas[t2] < topic_counts[t2]:
                    quotas[t2] += 1
                    remaining -= 1

    # In edge cases where rounding assigned more than desired (should be rare), trim from largest quotas
    while sum(quotas.values()) > desired_count:
        # find topic with largest quota > 1 and reduce by 1
        candidates = [t for t, q in quotas.items() if q > 1]
        if not candidates:
            break
        # pick the one with largest current quota
        tmax = max(candidates, key=lambda x: quotas[x])
        quotas[tmax] -= 1

    # Now sample from each topic according to final quotas
    selected_questions = []
    for t, q in quotas.items():
        rows = topic_groups[t].copy()
        # sample without replacement q items
        if q >= len(rows):
            chosen = rows
        else:
            chosen = random.sample(rows, q)
        for r in chosen:
            selected_questions.append(build_question_from_row(r))

    # Final shuffle of selected questions
    random.shuffle(selected_questions)
    return selected_questions




# ------------------------------  
# SAVE RESULTS  
# ------------------------------  
def save_to_results_row(row):
    headers = [
    "register_number",
    "drive_index",
    "round",
    "score",
    "total",
    "attempted",
    "correct",
    "wrong",
    "marks_correct",
    "marks_wrong",
    "cheated",
    "submitted_at"
]



    RESULTS_CSV = "data/test_results.csv"
    file_exists = os.path.exists(RESULTS_CSV)

    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ------------------------------  
# SUBMIT ROUND (move to next)  
# ------------------------------  
@app.route("/student/test/submit/<int:drive_index>/<round>", methods=["POST"])
def submit_round(drive_index, round):
    reg_no = session.get("student_reg_no")

    df = load_company_drives()
    row = df.iloc[drive_index]

    raw_file = row.get(f"{round}_test_link", "")
    if not isinstance(raw_file, str):
        raw_file = ""

    filename = raw_file.replace("internal:", "").strip()
    if filename == "":
        return "Test file missing or not assigned by admin", 404

    questions = read_test_file(filename)

    import json
    answers = json.loads(request.form.get("answers_json", "[]"))
    cheated = int(request.form.get("cheated", 0))

    # -----------------------------------------
    # PREPARE VARIABLES FIRST
    # -----------------------------------------
    total = len(questions)
    attempted = 0
    correct = 0
    wrong = 0
    marks_correct = 5
    marks_wrong = -1

    # Count correct and wrong
    for i, q in enumerate(questions):
        chosen = answers[i]
        if chosen is not None:
            attempted += 1
            if int(chosen) == q["answer_index"]:
                correct += 1
            else:
                wrong += 1

    score = (correct * marks_correct) + (wrong * marks_wrong)

    # -----------------------------------------
    # CHEATING DETECTED → CANCEL TEST
    # -----------------------------------------
    if cheated == 1:
        save_to_results_row({
            "register_number": reg_no,
            "drive_index": drive_index,
            "round": round,
            "score": 0,
            "total": total,
            "attempted": attempted,
            "correct": correct,
            "wrong": wrong,
            "marks_correct": marks_correct,
            "marks_wrong": marks_wrong,
            "cheated": 1,
            "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return "❌ You have been disqualified for cheating. Test cancelled.", 403

    # -----------------------------------------
    # SAVE NORMAL ATTEMPT
    # -----------------------------------------
    save_to_results_row({
        "register_number": reg_no,
        "drive_index": drive_index,
        "round": round,
        "score": score,
        "total": total,
        "attempted": attempted,
        "correct": correct,
        "wrong": wrong,
        "marks_correct": marks_correct,
        "marks_wrong": marks_wrong,
        "cheated": 0,
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    # CONTINUE TO NEXT ROUND
    if round == "aptitude":
        return redirect(url_for("round_instructions", drive_index=drive_index, round="domain"))

    if round == "domain":
        return redirect(url_for("round_instructions", drive_index=drive_index, round="coding"))

    return redirect(url_for("test_summary", drive_index=drive_index))



# ----------------------------------
# GENERATE RESUME FROM STUDENT DATA
# ----------------------------------
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

def safe_number(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default

def parse_resume_list(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass

    return [item.strip() for item in text.split(",") if item.strip()]

def draw_wrapped_text(pdf, text, x, y, max_width, font_name="Helvetica", font_size=10.5, leading=14, color=colors.black):
    pdf.setFillColor(color)
    pdf.setFont(font_name, font_size)

    words = str(text).split()
    if not words:
        return y

    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        if pdf.stringWidth(test_line, font_name, font_size) <= max_width:
            line = test_line
        else:
            pdf.drawString(x, y, line)
            y -= leading
            line = word

    if line:
        pdf.drawString(x, y, line)
        y -= leading

    return y

def draw_bullet_list(pdf, items, x, y, max_width, bullet_color=colors.HexColor("#C6952A")):
    for item in items:
        pdf.setFillColor(bullet_color)
        pdf.circle(x + 2, y + 3, 1.8, fill=1, stroke=0)
        y = draw_wrapped_text(
            pdf,
            item,
            x + 12,
            y,
            max_width - 12,
            font_name="Helvetica",
            font_size=10.2,
            leading=13,
            color=colors.HexColor("#222222")
        )
        y -= 3
    return y

def draw_section_heading(pdf, title, x, y, width):
    pdf.setFillColor(colors.HexColor("#1A1A1A"))
    pdf.setFont("Helvetica-Bold", 12.5)
    pdf.drawString(x, y, title.upper())
    pdf.setStrokeColor(colors.HexColor("#E2B04A"))
    pdf.setLineWidth(1.2)
    pdf.line(x, y - 4, x + width, y - 4)
    return y - 20

def ensure_resume_space(pdf, y, needed_height, page_width, page_height):
    if y - needed_height < 50:
        pdf.showPage()
        pdf.setFillColor(colors.black)
        return page_height - 55
    return y

@app.route("/student/generate_resume")
def generate_resume():

    if "student_reg_no" not in session:
        return redirect(url_for("login"))

    reg_no = session["student_reg_no"]

    df = load_students()
    student = df[df["Register_Number"] == reg_no].iloc[0]
    cert_list = []

    if os.path.exists(CERT_CSV):

        cert_df = pd.read_csv(CERT_CSV)

        student_certs = cert_df[
            (cert_df["register_number"] == reg_no) &
            (cert_df["status"] == "approved")
        ]

        cert_list = student_certs["certificate_name"].tolist()

    filename = f"{reg_no}_generated_resume.pdf"
    path = os.path.join(RESUME_DIR, filename)

    c = canvas.Canvas(path, pagesize=A4)

    width, height = A4
    left_margin = 48
    right_margin = width - 48
    content_width = right_margin - left_margin
    y = height - 48

    cgpa = safe_number(student.get("CGPA", 0))
    semester = student.get("Current_Sem", "")
    projects = int(safe_number(student.get("Projects_Done", 0)))
    hackathons = int(safe_number(student.get("Hackathons_Participated", 0)))
    patents = int(safe_number(student.get("Patents_Granted", 0)))
    papers = int(safe_number(student.get("Research_Papers_Published", 0)))
    communication = safe_number(student.get("Avg_Communication_Score", 0))
    aptitude = safe_number(student.get("Weekly_Aptitude_Avg", 0))
    leetcode = int(safe_number(student.get("LeetCode_Problems_Solved", 0)))
    codechef = int(safe_number(student.get("CodeChef_Rating", 0)))
    skill_index = safe_number(student.get("skill_index", 0))

    certification_names = cert_list[:]
    if not certification_names:
        certification_names = parse_resume_list(student.get("Certifications_List", ""))

    certification_names = certification_names[:6]

    skill_items = []
    department = str(student.get("Department", "")).strip()
    if department:
        skill_items.append(f"Domain Focus: {department}")
    if leetcode > 0:
        skill_items.append(f"Problem Solving: {leetcode} LeetCode problems solved")
    if codechef > 0:
        skill_items.append(f"Competitive Coding: CodeChef rating {codechef}")
    if communication > 0:
        skill_items.append(f"Communication: Average score {communication:.0f}")
    if aptitude > 0:
        skill_items.append(f"Aptitude: Weekly average {aptitude:.0f}")
    foreign_language = str(student.get("Foreign_Language_Known", "")).strip()
    if foreign_language and foreign_language.lower() != "nan":
        skill_items.append(f"Additional Language: {foreign_language}")

    achievement_items = [
        f"Maintained a CGPA of {cgpa:.2f} in Semester {semester}" if cgpa else "",
        f"Completed {projects} academic or practical projects" if projects else "",
        f"Participated in {hackathons} hackathons, demonstrating team-based problem solving" if hackathons else "",
        f"Published {papers} research or review papers" if papers else "",
        f"Holds {patents} patent grants" if patents else "",
        f"Built a skill index score of {skill_index:.0f} based on academic and profile performance" if skill_index else "",
    ]
    achievement_items = [item for item in achievement_items if item]

    summary_parts = []
    if department:
        summary_parts.append(f"{department} student")
    if semester:
        summary_parts.append(f"currently in semester {semester}")
    if cgpa:
        summary_parts.append(f"with a CGPA of {cgpa:.2f}")
    base_summary = " ".join(summary_parts).strip()
    if base_summary:
        base_summary = base_summary[0].upper() + base_summary[1:]

    profile_summary = (
        f"{base_summary}. Strong interest in technology-driven roles with proven exposure to projects, "
        f"coding practice, certifications, and campus-level achievement metrics. Seeking opportunities in "
        f"fast-paced teams where analytical thinking, learning agility, and execution matter."
    ).replace("..", ".")

    c.setFillColor(colors.HexColor("#F7F1E1"))
    c.rect(0, height - 130, width, 130, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#E2B04A"))
    c.rect(0, height - 18, width, 18, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#1A1A1A"))
    c.setFont("Helvetica-Bold", 23)
    c.drawString(left_margin, height - 62, str(student.get("Student_Name", "Student")).upper())

    c.setFont("Helvetica", 10.8)
    contact_line = " | ".join([
        f"Register No: {student.get('Register_Number', '')}",
        f"Department: {department}",
        f"Semester: {semester}",
        f"CGPA: {cgpa:.2f}" if cgpa else "CGPA: -"
    ])
    c.drawString(left_margin, height - 86, contact_line)

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawString(left_margin, height - 104, "Professional student resume generated from verified portal profile data")

    y = height - 158

    y = draw_section_heading(c, "Profile Summary", left_margin, y, content_width)
    y = draw_wrapped_text(
        c,
        profile_summary,
        left_margin,
        y,
        content_width,
        font_name="Helvetica",
        font_size=10.6,
        leading=15,
        color=colors.HexColor("#222222")
    )
    y -= 6

    y = ensure_resume_space(c, y, 115, width, height)
    y = draw_section_heading(c, "Education Snapshot", left_margin, y, content_width)
    education_points = [
        f"Programme: {department}" if department else "",
        f"Current Semester: {semester}" if semester != "" else "",
        f"Current CGPA: {cgpa:.2f}" if cgpa else "",
        f"Student ID: {student.get('Student_ID', '')}" if str(student.get('Student_ID', '')).strip() else "",
    ]
    education_points = [point for point in education_points if point]
    y = draw_bullet_list(c, education_points, left_margin, y, content_width)

    y = ensure_resume_space(c, y, 130, width, height)
    y = draw_section_heading(c, "Technical & Professional Highlights", left_margin, y, content_width)
    y = draw_bullet_list(c, skill_items or ["Profile skills will appear here after adding more academic and coding data."], left_margin, y, content_width)

    y = ensure_resume_space(c, y, 130, width, height)
    y = draw_section_heading(c, "Achievements", left_margin, y, content_width)
    y = draw_bullet_list(c, achievement_items or ["Academic and activity achievements will appear here once updated in the profile."], left_margin, y, content_width)

    y = ensure_resume_space(c, y, 120, width, height)
    y = draw_section_heading(c, "Certifications", left_margin, y, content_width)
    cert_points = certification_names or ["No approved certifications available in the portal yet."]
    y = draw_bullet_list(c, cert_points, left_margin, y, content_width)

    y = ensure_resume_space(c, y, 70, width, height)
    y = draw_section_heading(c, "Recruiter Quick View", left_margin, y, content_width)
    quick_view = (
        f"Projects: {projects}    |    Hackathons: {hackathons}    |    Research Papers: {papers}    |    "
        f"Patents: {patents}    |    Skill Index: {skill_index:.0f}"
    )
    y = draw_wrapped_text(c, quick_view, left_margin, y, content_width, font_name="Helvetica-Bold", font_size=10.4, leading=14, color=colors.HexColor("#222222"))

    c.save()

    return send_file(path, as_attachment=True)
# ------------------------------
# LOGOUT
# ------------------------------
@app.route("/logout")
def logout():
    session.pop("student_reg_no", None)
    return redirect(url_for("login"))


# ------------------------------
# RUN
# ------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5002)
