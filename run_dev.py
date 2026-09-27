"""
run_dev.py
-----------------------------------------------------------------------------
Starts the Flask backend AND the Vite React dev server together, from one
terminal, with one command:

    python run_dev.py

Ctrl+C kills both cleanly. This is for ACTIVE FRONTEND DEVELOPMENT — you
still get React's hot-reload. If you don't need hot-reload and just want
Flask to serve the built React app on its own (true single process, no
second port at all), use the "Flask serves the build" setup instead
(see README section 2) — that skips this script entirely.

Place this file at your project root, next to app_new.py and Frontend/.
Adjust FRONTEND_DIR below if your React folder is named differently.
"""

import subprocess
import sys
import os
import signal
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "Frontend")   # ⚠️ adjust if your folder name differs

processes = []


def start(cmd, cwd, name):
    print(f"▶ starting {name}: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=(os.name == "nt"),  # npm needs shell=True on Windows
    )
    processes.append((name, proc))
    return proc


def shutdown(*_):
    print("\n⏹  stopping all processes...")
    for name, proc in processes:
        print(f"  stopping {name} (pid {proc.pid})")
        proc.terminate()
    time.sleep(1)
    for name, proc in processes:
        if proc.poll() is None:
            proc.kill()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if not os.path.isdir(FRONTEND_DIR):
        print(f"❌ Frontend dir not found at {FRONTEND_DIR}. Edit FRONTEND_DIR in run_dev.py.")
        sys.exit(1)

    # Backend — same command you already use
    start([sys.executable, "app_new.py"], cwd=BASE_DIR, name="flask")

    # Frontend — Vite dev server
    start(["npm", "run", "dev"], cwd=FRONTEND_DIR, name="vite")

    print("\n✅ Both servers starting.")
    print("   Flask : http://localhost:5000")
    print("   Vite  : http://localhost:5173")
    print("   Ctrl+C to stop both.\n")

    # Wait on whichever process ends first (or both run forever until Ctrl+C)
    try:
        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"⚠️  {name} exited with code {proc.returncode}")
                    shutdown()
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()
