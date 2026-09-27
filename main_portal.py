import threading
import time
import os
import sys
from flask import Flask, render_template

# ---------------------------------------------------
# FIX PATHS
# ---------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def resource_path(relative):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(BASE_DIR, relative)

template_folder = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, template_folder=template_folder)

# ---------------------------------------------------
# IMPORT-BASED SERVER START (NO SUBPROCESS, NO EXE LOOP)
# ---------------------------------------------------
def start_admin():
    import app as admin_app
    admin_app.app.run(port=5001, debug=False)

def start_student():
    import student_portal as stu_app
    stu_app.app.run(port=5002, debug=False)

def start_company():
    import company_portal as comp_app
    comp_app.app.run(port=5003, debug=False)

# ---------------------------------------------------
# RUN OTHER PORTALS IN THREADS
# ---------------------------------------------------
def start_portals():
    time.sleep(1)

    threading.Thread(target=start_admin, daemon=True).start()
    threading.Thread(target=start_student, daemon=True).start()
    threading.Thread(target=start_company, daemon=True).start()

threading.Thread(target=start_portals, daemon=True).start()

# ---------------------------------------------------
# MAIN PORTAL
# ---------------------------------------------------
@app.route("/")
def home():
    return render_template("main_portal.html")

if __name__ == "__main__":
    app.run(port=5000, debug=False)
