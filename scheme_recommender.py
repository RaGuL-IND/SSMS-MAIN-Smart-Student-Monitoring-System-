import pandas as pd
import pickle
import os
import re

# -----------------------------
# PATH SETUP
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(BASE_DIR, "model", "scheme_predictor_v2_rf.pkl")
SCHEMES_CSV = os.path.join(BASE_DIR, "data", "schemes_final_expanded.csv")

# -----------------------------
# LOAD MODEL SAFELY
# -----------------------------
model = None

try:
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        print("ML model loaded successfully")
    else:
        print("Model file not found:", MODEL_PATH)

except Exception as e:
    print("Model loading failed:", e)
    print("Portal will continue without ML recommendations")

# -----------------------------
# CERTIFICATE PARSING
# -----------------------------
def parse_cert_item(cert_item):
    m = re.match(r"(.+?)\s*\((\d{4}-\d{2}-\d{2})\)\s*$", str(cert_item).strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return str(cert_item).strip(), None


KEYWORDS = [
    "python","ai","ml","machine learning","machine","learning","deep","neural",
    "cloud","aws","azure","gcp","devops",
    "robot","robotics","iot","embedded",
    "cyber","security","hacking","forensics",
    "data","analytics","analysis","pandas","numpy","statistics",
    "blockchain","web3","smart contract",
    "quantum","physics",
    "space","aero","astrophysics","satellite","remote sensing","gis",
    "agri","agriculture","iot",
    "innovation","hackathon","coding","dsa","algorithms"
]


def extract_student_skills(cert_list_str):

    if pd.isna(cert_list_str) or str(cert_list_str).strip() == "":
        return "none"

    text = str(cert_list_str).lower()
    found = set()

    parts = [p.strip() for p in text.split(",") if p.strip()]

    for p in parts:

        name, date = parse_cert_item(p)
        name_l = name.lower()

        for k in KEYWORDS:
            if k in name_l:
                token = k.replace(" ", "_")
                found.add(token)

    if not found:
        return "none"

    return " ".join(sorted(found))


# -----------------------------
# ML RECOMMENDATION FUNCTION
# -----------------------------
def ml_recommend_schemes(student):

    if not os.path.exists(SCHEMES_CSV):
        print("Schemes dataset missing")
        return []

    schemes_df = pd.read_csv(SCHEMES_CSV)

    results = []

    student_skill_str = extract_student_skills(
        student.get("Certifications_List_With_Date", "") or
        student.get("Cert_List", "")
    )

    for _, row in schemes_df.iterrows():

        req = row.get("Required_Certifications", "")

        if pd.isna(req) or str(req).strip() == "":
            req = "none"

        probability = 50
        pred = 0

        # ----------------------------------
        # USE ML MODEL IF AVAILABLE
        # ----------------------------------
        if model is not None:

            try:

                X = pd.DataFrame([{
                    "CGPA": float(student.get("CGPA", 0)),
                    "Cert_Count": int(student.get(
                        "Number_of_Certifications",
                        student.get("Cert_Count", 0)
                    )),
                    "Gender": student.get("Gender", "Male"),
                    "Government_Scheme": row["Scheme_Name"],
                    "Scheme_Required_Certifications":
                        req.replace(",", "/").replace(" ", "_"),
                    "Student_Skills": student_skill_str
                }])

                proba = model.predict_proba(X)

                if proba.shape[1] == 1:
                    probability = proba[0][0] * 100
                else:
                    probability = proba[0][1] * 100

                pred = int(model.predict(X)[0])

            except Exception as e:
                print("Prediction error:", e)

        # ----------------------------------
        # ADD RESULT
        # ----------------------------------
        results.append({

            "name": row["Scheme_Name"],
            "benefits": row.get("Benefits", ""),
            "apply_link": row.get("Apply_Link", "#"),
            "probability": round(probability, 2),
            "predicted": pred

        })

    results = sorted(results, key=lambda x: x["probability"], reverse=True)

    return results