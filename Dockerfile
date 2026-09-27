# ================================================================
# Internship & Placement Portal — Dockerfile
# Multi-stage: build wheels, then copy into slim runtime image.
# ================================================================

# --- Stage 1: Builder (installs dependencies) ---
FROM python:3.12-slim AS builder

WORKDIR /app

# System deps needed to compile some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a dedicated prefix so we can COPY them
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# --- Stage 2: Runtime (lean image) ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create persistent data directories
RUN mkdir -p data/certificates data/resumes data/tests model static/css

# Expose Flask/Gunicorn port
EXPOSE 5000

# Use gunicorn as the production WSGI server.
# Workers = (2 × CPU cores) + 1 is the standard recommendation.
CMD ["gunicorn", \
     "--config", "gunicorn.conf.py", \
     "app_new:app"]
