# AI Intigrate Coding - containerized agent + web frontend.
# Build:
#   docker build -t ai-agent .
# Run (frontend):
#   docker compose up --build
# Run (CLI):
#   docker compose run --rm cli "build a Flask API for a task tracker"
FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Python deps first (better layer caching).
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt

# Install Chromium (headless shell) for the browser-backed research + web-sourcing tools.
RUN playwright install --with-deps chromium

# Application source.
COPY . .

# The web frontend fires `python -m agent <task>` in a subprocess from the repo root.
# Bind to all interfaces so Docker port mapping works; port/host overridable via env.
ENV FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000

EXPOSE 5000

# Default: the web UI. Override with `docker compose run --rm cli <task>`.
CMD ["python", "frontend/app.py"]