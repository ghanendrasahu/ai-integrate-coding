# AI Integrate Coding - containerized agent + web frontend.
# Build:
#   docker build -t ai-agent .
# Run (frontend):
#   docker compose up --build
# Run (CLI):
#   docker compose run --rm cli "build a Flask API for a task tracker"
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright

WORKDIR /app

# Python deps from the pinned lock (dev/test/type tools filtered out).
COPY requirements.lock ./
RUN grep -vE '^(pytest==|pyright==)' requirements.lock > runtime.lock \
    && pip install --no-cache-dir -r runtime.lock

# Chromium (headless) for the browser-backed research + web-sourcing tools.
RUN playwright install --with-deps chromium

# Non-root runtime: appuser owns the app, its workspace bind target and the
# browser cache; $HOME keeps any accidental writes out of root paths.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/workspace \
    && chown -R appuser /app /opt/ms-playwright /home/appuser

# Application source. .dockerignore keeps .env, workspace and caches out.
COPY --chown=appuser . .

# The web frontend fires `python -m agent <task>` in a subprocess from the repo root.
# Bind to all interfaces so Docker port mapping works; port/host overridable via env.
ENV FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=4)" || exit 1

# Default: the web UI. Override with `docker compose run --rm cli <task>`.
CMD ["python", "frontend/app.py"]
