from scheme_recommender import MODEL_PATH
from auth_decorators import admin_required
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import pandas as pd
import os
import numpy as np
import json
from io import StringIO
from datetime import datetime
from utils import (
    create_admin, verify_admin, merge_upload_df, read_master_df,
    read_recycle_df, save_master_df, save_recycle_df,
    compute_skill_index_for_row, compute_analysis_from_df, parse_list_field
)

admin_bp = Blueprint("admin", __name__)

# Paths resolved relative to the main project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CERT_UPLOAD_DIR = os.path.join(DATA_DIR, "certificates")
RESUME_DIR = os.path.join(DATA_DIR, "resumes")
RESUME_EXPORT_CSV = os.path.join(DATA_DIR, "resume_export.csv")
CERT_CSV = os.path.join(DATA_DIR, "certificates.csv")
MASTER_CSV = os.path.join(DATA_DIR, "master_students.csv")
RECYCLE_CSV = os.path.join(DATA_DIR, "recycle_bin.csv")
COMPANY_DRIVES = os.path.join(DATA_DIR, "company_drives.csv")
TESTS_DIR = os.path.join(DATA_DIR, "tests")
RESULTS_CSV = os.path.join(DATA_DIR, "test_results.csv")

def read_company_drives():
    if not os.path.exists(COMPANY_DRIVES):
        return pd.DataFrame()
    return pd.read_csv(COMPANY_DRIVES)

def load_company_drives():
    return read_company_drives()

def save_company_drives(df):
    df.to_csv(COMPANY_DRIVES, index=False)

# ----------------------------------------------
# AUTH
# ----------------------------------------------

@admin_bp.route("/", methods=["GET", "POST"])
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    # Redirect to React login page (new centralized login)
    if request.method == "GET":
        return redirect("/")

@admin_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        try:
            create_admin(username, password)
            flash("Admin created! Please login.")
            return redirect(url_for("admin.login"))
        except ValueError as e:
            flash(str(e))
    return render_template("register.html")

@admin_bp.route("/certificates")
@admin_required
def admin_certificates():
    # ── DB path ──────────────────────────────────────────────────────────
    try:
        from models import Certificate, db
        db.session.execute(db.select(Certificate).limit(1))   # probe
        pending_objs = Certificate.query.filter(
            Certificate.status.in_(["pending", "Pending"])
        ).order_by(Certificate.id.desc()).all()
        certs = [{
            "certificate_id": c.certificate_id,
            "register_number": c.register_number,
            "student_name":    c.student_name,
            "certificate_name":c.certificate_name,
            "file_path":       c.file_path or "",
            "status":          c.status,
            "uploaded_at":     c.uploaded_at or "",
        } for c in pending_objs]
        return render_template("admin_certificates.html", certs=certs)
    except Exception:
        pass

    # ── CSV fallback ──────────────────────────────────────────────────────
    if not os.path.exists(CERT_CSV):
        return render_template("admin_certificates.html", certs=[])

    df = pd.read_csv(CERT_CSV)
    df.columns = df.columns.str.strip()
    if "file_path" not in df.columns:
        df["file_path"] = ""
    df["file_path"] = df["file_path"].fillna("").astype(str).str.strip()
    df["certificate_id"] = pd.to_numeric(df["certificate_id"], errors="coerce").fillna(0).astype(int)
    pending = df[df["status"].str.lower() == "pending"]
    return render_template("admin_certificates.html", certs=pending.to_dict(orient="records"))

@admin_bp.route("/certificates/review/<int:cert_id>", methods=["POST"])
@admin_required
def review_certificate(cert_id):
    action  = request.form.get("action")
    remarks = request.form.get("remarks", "")
    new_status  = "approved" if action == "approve" else "rejected"
    reviewed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    reviewer    = session["admin_user"]

    reg_no    = None
    cert_name = None

    # ── DB path ──────────────────────────────────────────────────────────
    db_used = False
    try:
        from models import Certificate, db
        cert_obj = Certificate.query.filter_by(certificate_id=str(cert_id)).first()
        if cert_obj:
            cert_obj.status      = new_status
            cert_obj.reviewed_by = reviewer
            cert_obj.reviewed_at = reviewed_at
            cert_obj.remarks     = remarks
            db.session.commit()
            reg_no    = cert_obj.register_number
            cert_name = cert_obj.certificate_name
            db_used   = True
        else:
            flash("Certificate not found")
            return redirect(url_for("admin.admin_certificates"))
    except Exception:
        pass

    # ── CSV mirror / fallback ─────────────────────────────────────────────
    if os.path.exists(CERT_CSV):
        try:
            df  = pd.read_csv(CERT_CSV)
            idx = df[df["certificate_id"] == cert_id].index
            if not idx.empty:
                df.at[idx[0], "status"]      = new_status
                df.at[idx[0], "reviewed_by"] = reviewer
                df.at[idx[0], "reviewed_at"] = reviewed_at
                df.at[idx[0], "remarks"]     = remarks
                if not db_used:
                    reg_no    = str(df.at[idx[0], "register_number"])
                    cert_name = df.at[idx[0], "certificate_name"]
                df.to_csv(CERT_CSV, index=False)
        except Exception:
            pass

    # ── On approval: update student record ───────────────────────────────
    if action == "approve" and reg_no and cert_name:
        master    = read_master_df()
        stu_idx   = master[master["Register_Number"].astype(str) == reg_no].index
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

    flash(f"Certificate {action}d successfully")
    return redirect(url_for("admin.admin_certificates"))

@admin_bp.route("/logout")
def logout():
    session.pop("admin_user", None)
    flash("Logged out successfully.")
    return redirect("/")  # Redirect to React login page

# ----------------------------------------------
# DASHBOARD
# ----------------------------------------------

@admin_bp.route("/certificates/view/<path:filename>")
@admin_required
def view_certificate_file(filename):
    file_path = os.path.join(CERT_UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    return send_file(file_path)

@admin_bp.route("/resumes/view/<path:filename>")
@admin_required
def view_resume_file(filename):
    file_path = os.path.join(RESUME_DIR, filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    return send_file(file_path)

@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    return render_template("dashboard.html", user=session["admin_user"])

@admin_bp.route("/drives")
@admin_required
def drives():
    drives_df = read_company_drives()
    return render_template("drives.html", drives=drives_df)

@admin_bp.route("/drives/<int:drive_id>")
@admin_required
def view_drive_eligibility(drive_id):
    drives_df = read_company_drives()
    if drive_id >= len(drives_df):
        flash("Invalid drive ID")
        return redirect(url_for("admin.drives"))

    company = drives_df.iloc[drive_id]

    from utils import get_eligible_students_for_company
    students = get_eligible_students_for_company(company)

    sort_order = request.args.get("sort", "none")
    if sort_order == "asc":
        students = sorted(students, key=lambda x: float(x.get("skill_index", 0)))
    elif sort_order == "desc":
        students = sorted(students, key=lambda x: float(x.get("skill_index", 0)), reverse=True)

    return render_template(
        "eligible_students.html",
        company=company,
        students=students,
        sort_order=sort_order
    )

@admin_bp.route("/assign_test/<int:drive_index>", methods=["GET", "POST"])
@admin_required
def admin_assign_test(drive_index):
    df = load_company_drives()
    if df.empty or drive_index >= len(df):
        flash("Invalid drive index")
        return redirect(url_for("admin.drives"))

    if request.method == "POST":
        files = {
            "aptitude": request.files.get("aptitude_test"),
            "domain": request.files.get("domain_test"),
            "coding": request.files.get("coding_test"),
        }

        durations = {
            "aptitude": request.form.get("aptitude_duration", "30"),
            "domain": request.form.get("domain_duration", "30"),
            "coding": request.form.get("coding_duration", "30"),
        }

        for test_type, uploaded_file in files.items():
            if uploaded_file and uploaded_file.filename.endswith(".csv"):
                filename = f"{test_type}_{drive_index}_{uploaded_file.filename}"
                file_path = os.path.join(TESTS_DIR, filename)
                uploaded_file.save(file_path)

                df.at[drive_index, f"{test_type}_test_link"] = f"internal:{filename}"
                df.at[drive_index, f"{test_type}_duration"] = durations[test_type]

        save_company_drives(df)
        flash("Tests uploaded and assigned successfully!")
        return redirect(url_for("admin.admin_assign_test", drive_index=drive_index))

    return render_template(
        "admin_assign_test.html",
        drive=df.iloc[drive_index],
        drive_index=drive_index
    )

# ----------------------------------------------
# ADD STUDENTS
# ----------------------------------------------

@admin_bp.route("/add_students", methods=["GET", "POST"])
@admin_required
def add_students():
    if request.method == "POST":
        file = request.files.get("file")
        filename = getattr(file, "filename", "") if file is not None else ""
        if not filename or not filename.lower().endswith(".csv"):
            flash("Please upload a CSV file")
            return redirect(url_for("admin.add_students"))
        df_upload = pd.read_csv(file)
        result = merge_upload_df(df_upload, session["admin_user"])
        flash(f"Upload complete: {result['updated']} records updated.")
        return redirect(url_for("admin.view_students"))

    return render_template("add_students.html")

# ----------------------------------------------
# VIEW STUDENTS
# ----------------------------------------------

@admin_bp.route("/view_students", methods=["GET", "POST"])
@admin_required
def view_students():
    df = read_master_df()
    if df.empty:
        flash("No student data available.")
        return render_template("view_students.html", students=[], semesters=[])

    if request.method == "POST":
        selected = request.form.getlist("selected_students")
        if not selected:
            flash("No students selected for deletion.")
            return redirect(url_for("admin.view_students"))

        master = read_master_df()
        recycle = read_recycle_df()
        moved = []

        for reg in selected:
            row = master[master["Register_Number"].astype(str) == str(reg)]
            if not row.empty:
                row_dict = row.iloc[0].to_dict()
                row_dict["deleted_at"] = datetime.utcnow().isoformat()
                row_dict["deleted_by"] = session["admin_user"]

                recycle = pd.concat([recycle, pd.DataFrame([row_dict])], ignore_index=True)
                master = master[master["Register_Number"].astype(str) != str(reg)]
                moved.append(reg)

        save_master_df(master)
        save_recycle_df(recycle)

        flash(f"Moved {len(moved)} students to recycle bin.")
        return redirect(url_for("admin.view_students"))

    batches = sorted(df["Batch"].dropna().unique())
    depts = sorted(df["Department"].dropna().unique())
    semesters = sorted(df["Current_Sem"].dropna().unique())

    batch_filter = request.args.get("batch")
    dept_filter = request.args.get("dept")
    sem_filter = request.args.get("current_sem")
    cgpa_filter_type = request.args.get("cgpa_filter_type")
    cgpa_value = request.args.get("cgpa_value")

    filtered_df = df.copy()

    if batch_filter and batch_filter != "all":
        filtered_df = filtered_df[filtered_df["Batch"] == batch_filter]

    if dept_filter and dept_filter != "all":
        filtered_df = filtered_df[filtered_df["Department"] == dept_filter]

    if sem_filter and sem_filter != "all":
        filtered_df = filtered_df[filtered_df["Current_Sem"] == int(sem_filter)]

    if cgpa_filter_type and cgpa_value:
        try:
            cgpa_value = float(cgpa_value)
            if cgpa_filter_type == "greater":
                filtered_df = filtered_df[filtered_df["CGPA"] > cgpa_value]
            elif cgpa_filter_type == "less":
                filtered_df = filtered_df[filtered_df["CGPA"] < cgpa_value]
        except ValueError:
            pass

    students = filtered_df.to_dict(orient="records")

    return render_template(
        "view_students.html",
        students=students,
        batches=batches,
        depts=depts,
        semesters=semesters
    )

@admin_bp.route("/student/<reg_no>")
@admin_required
def student_profile(reg_no):
    df = read_master_df()
    if df.empty:
        flash("No student data available.")
        return redirect(url_for("admin.view_students"))

    reg_no = str(reg_no)
    student = df[df["Register_Number"].astype(str) == reg_no]
    if student.empty:
        flash("Student not found.")
        return redirect(url_for("admin.view_students"))

    student_data = student.to_dict(orient="records")[0]

    semesters = []
    for i in range(1, 11):
        if f"Sem{i}_GPA" in df.columns:
            semesters.append(f"Sem{i}")

    return render_template(
        "student_profile.html",
        student=student_data,
        semesters=semesters
    )

# ----------------------------------------------
# CGPA ANALYSIS & RETRAINING
# ----------------------------------------------

@admin_bp.route("/analysis/retrain", methods=["POST"])
@admin_required
def admin_analysis_retrain():
    try:
        # Load actual student profiles
        df = read_master_df()
        if df.empty:
            return jsonify(success=False, message="No student data available to train model"), 400

        features_list = []
        for _, row in df.iterrows():
            cgpa = float(row.get("CGPA", 0))
            projects = float(row.get("Projects_Done", 0))
            papers = float(row.get("Research_Papers_Published", 0))
            hackathons = float(row.get("Hackathons_Participated", 0))
            academic_score = cgpa * 10 + projects * 4 + papers * 8 + hackathons * 5

            # Compute cert score based on weights
            levels = str(row.get("Certificate_Course_Level", "")).split(",")
            platforms = str(row.get("Certificate_Platform", "")).split(",")
            domains = str(row.get("Certificate_Domain", "")).split(",")

            level_weight = {"Beginner": 5, "Intermediate": 10, "Advanced": 15, "Professional": 20}
            platform_weight = {"Coursera": 1.4, "Google": 1.4, "Microsoft": 1.4, "Cisco": 1.5, "NPTEL": 1.5, "Udemy": 1.2}
            domain_weight = {"AI": 1.5, "Data Science": 1.4, "Cybersecurity": 1.4, "Cloud Computing": 1.3, "Programming": 1.2, "Networking": 1.2}

            cert_score = 0
            for i in range(len(levels)):
                lvl = levels[i].strip()
                plat = platforms[i].strip() if i < len(platforms) else ""
                dom = domains[i].strip() if i < len(domains) else ""
                base = level_weight.get(lvl, 5)
                pw = platform_weight.get(plat, 1.0)
                dw = domain_weight.get(dom, 1.0)
                cert_score += base * pw * dw

            cert_count = float(row.get("Number_of_Certifications", 0))
            features_list.append([academic_score, cert_score, cert_count, hackathons])

        actual_X = pd.DataFrame(features_list, columns=["academic_score", "certificate_score", "certificate_count", "hackathons"])

        # Calculate targets for actual data
        actual_indices = 0.5 * actual_X["academic_score"] + 0.5 * actual_X["certificate_score"]
        actual_y = []
        for idx in actual_indices:
            idx = min(idx, 100)
            if idx < 40:
                actual_y.append(0)
            elif idx < 60:
                actual_y.append(1)
            elif idx < 80:
                actual_y.append(2)
            else:
                actual_y.append(3)
        actual_y = np.array(actual_y)

        # Generate synthetic data for robust training
        np.random.seed(42)
        num_synthetic = 1000

        sys_cgpa = np.random.uniform(5.0, 10.0, num_synthetic)
        sys_projects = np.random.randint(0, 8, num_synthetic)
        sys_papers = np.random.randint(0, 4, num_synthetic)
        sys_hackathons = np.random.randint(0, 10, num_synthetic)
        sys_cert_count = np.random.randint(0, 20, num_synthetic)

        # Generate academic score
        sys_academic = sys_cgpa * 10 + sys_projects * 4 + sys_papers * 8 + sys_hackathons * 5

        # Generate certificate score
        sys_cert_score = sys_cert_count * np.random.uniform(8.0, 18.0, num_synthetic)

        synthetic_X = pd.DataFrame({
            "academic_score": sys_academic,
            "certificate_score": sys_cert_score,
            "certificate_count": sys_cert_count.astype(float),
            "hackathons": sys_hackathons.astype(float)
        })

        # Calculate targets for synthetic data
        synthetic_indices = 0.5 * synthetic_X["academic_score"] + 0.5 * synthetic_X["certificate_score"]
        synthetic_y = []
        for idx in synthetic_indices:
            idx = min(idx, 100)
            if idx < 40:
                synthetic_y.append(0)
            elif idx < 60:
                synthetic_y.append(1)
            elif idx < 80:
                synthetic_y.append(2)
            else:
                synthetic_y.append(3)
        synthetic_y = np.array(synthetic_y)

        # Combine datasets
        X = pd.concat([actual_X, synthetic_X], ignore_index=True)
        y = np.concatenate([actual_y, synthetic_y])

        import joblib
        from sklearn.ensemble import RandomForestClassifier

        clf = RandomForestClassifier(n_estimators=100, random_state=42)
        clf.fit(X, y)

        # Save model
        joblib.dump(clf, MODEL_PATH)

        # Dynamically reload in memory
        import utils
        utils.MODEL = clf

        # Recompute skill index for all students
        master = read_master_df()
        master["skill_index"] = master.apply(compute_skill_index_for_row, axis=1)
        from utils import classify_skill_level
        master["skill_level"] = master["skill_index"].apply(classify_skill_level)
        save_master_df(master)

        return jsonify(success=True, message="Skill Index ML model retrained successfully and all student profiles updated.")

    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@admin_bp.route("/analysis")
@admin_required
def analysis_index():
    return render_template("analysis.html")

@admin_bp.route("/analysis/upload", methods=["POST"])
def admin_analysis_upload():
    if "admin_user" not in session:
        return jsonify(success=False, message="Unauthorized"), 401

    file = request.files.get("file")
    if not file:
        return jsonify(success=False, message="No file provided")

    try:
        df = pd.read_csv(file)
        sem = request.form.get("sem")
        result = compute_analysis_from_df(df, sem)
        return jsonify(success=True, analysis=result)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@admin_bp.route("/analysis/bucket_students", methods=["POST"])
def analysis_bucket_students():
    if "admin_user" not in session:
        return jsonify(success=False, message="Unauthorized"), 401

    data = request.get_json()
    subject = data.get("subject")
    low = float(data.get("low", 0))
    high = float(data.get("high", 0))
    csv_text = data.get("csv")

    if not subject or csv_text is None:
        return jsonify(success=False, message="Missing parameters"), 400

    try:
        df = pd.read_csv(StringIO(csv_text))
        sem = data.get("sem")
        batch = data.get("batch")
        dept = data.get("dept")
        cgpa_type = data.get("cgpaType")
        cgpa_val = data.get("cgpaValue")

        if sem and sem != "all":
            df = df[df["Current_Sem"] == int(sem)]

        if batch and batch != "all":
            df = df[df["Batch"].astype(str).str.contains(batch, case=False)]

        if dept and dept != "all":
            df = df[df["Department"].astype(str).str.contains(dept, case=False)]

        if cgpa_type and cgpa_type != "none" and cgpa_val:
            cgpa_val = float(cgpa_val)
            if cgpa_type == "greater":
                df = df[df["CGPA"] > cgpa_val]
            elif cgpa_type == "less":
                df = df[df["CGPA"] < cgpa_val]

        raw_scores = []
        rows_for_subject = []

        for sem_num in range(1, 9):
            subj_col = f"Sem{sem_num}_Subjects"
            if subj_col not in df.columns:
                continue

            for idx, row in df.iterrows():
                subj_list = parse_list_field(row.get(subj_col, ""))
                if not subj_list:
                    continue

                ia1_list = parse_list_field(row.get(f"Sem{sem_num}_IA1", ""))
                ia2_list = parse_list_field(row.get(f"Sem{sem_num}_IA2", ""))
                model_list = parse_list_field(row.get(f"Sem{sem_num}_Model", ""))

                for i, subj in enumerate(subj_list):
                    if str(subj).strip() != subject:
                        continue

                    try:
                        ia1 = float(ia1_list[i]) if i < len(ia1_list) else 0
                    except: ia1 = 0
                    try:
                        ia2 = float(ia2_list[i]) if i < len(ia2_list) else 0
                    except: ia2 = 0
                    try:
                        model = float(model_list[i]) if i < len(model_list) else 0
                    except: model = 0

                    raw_total = ia1 + ia2 + model
                    raw_scores.append(raw_total)
                    rows_for_subject.append((row, raw_total))

        if not raw_scores:
            return jsonify(success=False, message="Subject not found"), 404

        max_raw = max(raw_scores)
        if max_raw <= 0:
            max_raw = 1

        matched = []
        for row, raw_total in rows_for_subject:
            norm = round((raw_total / max_raw) * 100, 2)
            if low <= norm <= high:
                matched.append({
                    "student_id": row.get("Student_ID"),
                    "register": row.get("Register_Number"),
                    "student_name": row.get("Student_Name"),
                    "score": norm,
                    "cgpa": row.get("CGPA"),
                })

        return jsonify(success=True, students=matched)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

# ----------------------------------------------
# DELETE / RECYCLE BIN
# ----------------------------------------------

@admin_bp.route("/delete_students", methods=["POST"])
def delete_students():
    if "admin_user" not in session:
        return redirect(url_for("admin.login"))
    regs = request.form.getlist("reg")
    if not regs:
        flash("No students selected.")
        return redirect(url_for("admin.view_students"))

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
    flash(f"Moved {len(moved)} students to recycle bin.")
    return redirect(url_for("admin.view_students"))

@admin_bp.route("/recycle_bin")
@admin_required
def recycle_bin():
    df = read_recycle_df()
    students = df.to_dict(orient="records")
    return render_template("recycle_bin.html", students=students)

@admin_bp.route("/restore", methods=["POST"])
def restore():
    if "admin_user" not in session:
        return redirect(url_for("admin.login"))
    regs = request.form.getlist("reg")
    recycle = read_recycle_df()
    master = read_master_df()
    restored = []
    for reg in regs:
        idx = recycle[recycle["Register_Number"].astype(str) == str(reg)].index
        if not idx.empty:
            row = recycle.loc[idx[0]].to_dict()
            for k in ["deleted_at", "deleted_by"]:
                row.pop(k, None)
            master = pd.concat([master, pd.DataFrame([row])], ignore_index=True)
            recycle = recycle.drop(index=idx)
            restored.append(reg)
    save_master_df(master)
    save_recycle_df(recycle)
    flash(f"Restored {len(restored)} students.")
    return redirect(url_for("admin.recycle_bin"))

@admin_bp.route("/permanent_delete", methods=["POST"])
def permanent_delete():
    regs = request.form.getlist("reg")
    recycle = read_recycle_df()
    for reg in regs:
        recycle = recycle[recycle["Register_Number"].astype(str) != str(reg)]
    save_recycle_df(recycle)
    flash("Deleted permanently.")
    return redirect(url_for("admin.recycle_bin"))

@admin_bp.route("/download_master")
@admin_required
def download_master():
    if not os.path.exists(MASTER_CSV):
        flash("No data available.")
        return redirect(url_for("admin.dashboard"))
    return send_file(MASTER_CSV, as_attachment=True)

@admin_bp.route("/resumes/download_csv")
@admin_required
def download_resume_csv():
    if not os.path.exists(RESUME_DIR):
        flash("No resumes available yet.")
        return redirect(url_for("admin.dashboard"))

    master_df = read_master_df()
    has_student_lookup = not master_df.empty and "Register_Number" in master_df.columns
    resume_rows = []

    for file_name in sorted(os.listdir(RESUME_DIR)):
        file_path = os.path.join(RESUME_DIR, file_name)
        if not os.path.isfile(file_path):
            continue

        reg_no = file_name.split("_", 1)[0].strip()
        student_row = pd.DataFrame()
        if has_student_lookup:
            student_row = master_df[master_df["Register_Number"].astype(str).str.strip() == reg_no]

        student_name = ""
        department = ""
        if not student_row.empty:
            student_name = str(student_row.iloc[0].get("Student_Name", "")).strip()
            department = str(student_row.iloc[0].get("Department", "")).strip()

        resume_rows.append({
            "register_number": reg_no,
            "student_name": student_name,
            "department": department,
            "resume_file_name": file_name,
            "resume_link": request.host_url.rstrip("/") + url_for("admin.view_resume_file", filename=file_name),
            "saved_at": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
        })

    if not resume_rows:
        flash("No resumes available yet.")
        return redirect(url_for("admin.dashboard"))

    export_df = pd.DataFrame(resume_rows)
    export_df.to_csv(RESUME_EXPORT_CSV, index=False)

    return send_file(
        RESUME_EXPORT_CSV,
        as_attachment=True,
        download_name="student_resumes_export.csv"
    )

@admin_bp.route("/test_results")
@admin_required
def admin_test_results():
    results_file = RESULTS_CSV
    if not os.path.exists(results_file):
        flash("No test results available yet.")
        return render_template("admin_test_results.html", results=[])

    df_results = pd.read_csv(results_file)
    df_drives = read_company_drives()
    df_drives["drive_index"] = df_drives.index

    merged = pd.merge(df_results, df_drives, on="drive_index", how="left")
    results = merged.to_dict(orient="records")

    return render_template("admin_test_results.html", results=results)

# ----------------------------------------------
# AI RESUME SEMANTIC SEARCH
# ----------------------------------------------

@admin_bp.route("/resumes/search")
@admin_required
def resume_search():
    return render_template("resume_search.html")

@admin_bp.route("/resumes/search/query", methods=["POST"])
@admin_required
def resume_search_query():
    query_text = request.form.get("query", "").strip()
    top_k = int(request.form.get("top_k", 5))

    if not query_text:
        return jsonify(success=False, message="Query is required"), 400

    try:
        from faiss_indexer import search_resumes
        raw_results = search_resumes(query_text, top_k=top_k)

        # Hydrate results with master student data details
        master_df = read_master_df()
        hydrated = []

        for item in raw_results:
            reg_no = item["register_number"]
            match = master_df[master_df["Register_Number"].astype(str).str.strip() == reg_no]
            if not match.empty:
                s_info = match.iloc[0]
                item["student_name"] = str(s_info.get("Student_Name", "Student")).strip()
                item["department"] = str(s_info.get("Department", "")).strip()
                item["cgpa"] = float(s_info.get("CGPA", 0))
                item["skill_index"] = float(s_info.get("skill_index", 0))
            else:
                item["student_name"] = "Unknown Student"
                item["department"] = "N/A"
                item["cgpa"] = "N/A"
                item["skill_index"] = "N/A"
            hydrated.append(item)

        return jsonify(success=True, results=hydrated)

    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@admin_bp.route("/resumes/search/rebuild", methods=["POST"])
@admin_required
def resume_rebuild_index():
    try:
        from faiss_indexer import build_resume_index
        success = build_resume_index()
        if success:
            return jsonify(success=True, message="FAISS semantic resume index rebuilt successfully.")
        else:
            return jsonify(success=False, message="No PDF resumes found or index build failed. Please upload resumes first.")
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

