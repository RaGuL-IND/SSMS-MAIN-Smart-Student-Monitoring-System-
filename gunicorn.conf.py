# ================================================================
# gunicorn.conf.py
# Production Gunicorn configuration for the Internship Portal.
# Override any value via environment variable if needed.
# ================================================================

import os
import multiprocessing

# --- Worker Configuration ---
# Formula: (2 × CPU cores) + 1
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"           # Use "gevent" for async; pip install gevent
threads = 2                     # Threads per worker
timeout = 120                   # Kill workers silent for > 120 s

# --- Binding ---
host = os.environ.get("HOST", "0.0.0.0")
port = int(os.environ.get("PORT", 5000))
bind = f"{host}:{port}"

# --- Logging ---
accesslog = "-"         # stdout
errorlog  = "-"         # stderr
loglevel  = os.environ.get("LOG_LEVEL", "info")

# --- Process naming (shows in `ps aux`) ---
proc_name = "internship_portal"

# --- Preload app to share memory between workers ---
preload_app = True
