# Changelog

All notable changes to this project are documented here. Released versions correspond to git tags.

## [0.8.1] - 2026-08-07

### Fixed

- CD publish failed on `ghcr.io` because the repository name contains uppercase letters (container registries require lowercase). The workflow now uses `docker/metadata-action` output for tags, which lowercases the image name, so releases push correctly. Also upgraded the Docker Actions to current majors.

## [0.8.0] - 2026-08-07

### Added

- **Continuous Delivery** (`.github/workflows/cd.yml`): pushing a `v*` tag builds the image and publishes it to GitHub Container Registry as both `<tag>` and `latest`. This completes the CI/CD pipeline (CI runs tests + builds the image; CD publishes releases).
- README: GHCR `docker pull` / `docker run` quick-start and a CI/CD overview.

## [0.7.4] - 2026-08-07

### Added

- `LICENSE` (MIT) and a matching README badge/tree entry, making the repo open to reuse by anyone with attribution.

## [0.7.3] - 2026-08-07

### Added

- `.env.example` configuration template (placeholder values, no secrets; un-ignored via `!.env.example` so it ships without exposing the real `.env`).
- CI now also builds the Docker image on every push/PR (catches packaging regressions like the earlier missing-Flask issue) via a new `docker-build` job.
- README CI + Python version badges.

## [0.7.2] - 2026-08-07

### Added

- `make.ps1` PowerShell wrapper mirroring the Makefile so `up` / `down` / `build` / `logs` / `shell` / `cli "<task>"` / `setup` / `test` / `lint` / `clean` work directly on Windows without `make` installed.
- README: shortcut usage split into PowerShell (`.\make.ps1 …`) and Git Bash / WSL / macOS (`make …`) variants.

## [0.7.1] - 2026-08-07

### Added

- `Makefile` convenience shortcuts: `up` / `down` / `build` / `cli TASK="..."` / `shell` / `logs` (Docker) and `setup` / `test` / `lint` / `clean` (local). `test` and `lint` auto-use `.venv/Scripts/python` when present.
- CI through GitHub Actions (`.github/workflows/ci.yml`): installs deps + Playwright Chromium and runs the full suite on every push/PR to `main`.
- README "Command shortcuts (Makefile)" section and updated project tree.

### Changed

- Removed on-disk `__pycache__` and `.pytest_cache` artifacts (gitignored, kept out of the repo).

## [0.7.0] - 2026-08-07

### Added

- **Docker packaging** to run the agent and its web frontend without any local Python or Playwright install:
  - `Dockerfile` built on `python:3.12-slim-bookworm` with bundled Chromium (`playwright install --with-deps chromium`) and Flask.
  - `docker-compose.yml` with two services:
    - `web` (default, `docker compose up`) — the control-plane frontend at `http://localhost:5000`.
    - `cli` (`docker compose run --rm cli "<task>"`) — one-shot command-line control.
  - Live code is bind-mounted for zero-rebuild iteration; `--sandbox` host-Docker-socket passthrough documented as an (explicitly security-guarded) comment.
  - `flask>=3.0.0` promoted into `requirements.txt` so the image (and any env) can run the frontend.
  - README "Run with Docker (easiest)" quick-start section and project-tree entries.

### Verified

- Image builds clean; containerized CLI `--help` and containerized frontend serve HTTP 200; headless Chromium inside the container launches and loads a live page.

## [0.6.1] - 2026-08-07

### Changed

- Embeddings are now cached **across** retriever builds (OpenAI and Ollama embedders share one process-wide cache), and the `Agent` reuses an unchanged retriever instead of rebuilding it each step. Notes are only re-embedded when they change, eliminating redundant embedding API calls and latency on every research step once the retrieval threshold is crossed.
- Added `RetrieverProtocol` import to `agent.py` required by the retriever reuse.

## [0.6.0] - 2026-08-07

### Changed

- `ask_web` now returns the best answer **plus a labeled comparison of every provider's reply** (marking the chosen one with `[CHOSEN]`), so the agent and the human reviewing a run log can verify why an answer was selected instead of relying on a single opaque result.
- `web_ai_profile/` added to `.gitignore` so persistent browser sessions are never committed.

### Added

- `CHANGELOG.md` documenting releases.
- Tests for the transparent answer formatter.

## [0.5.0] - 2026-08-07

### Added
- **Multi-app in-browser AI sourcing** (`agent/weblm.py`): the `ask_web` tool asks several browser-based AI assistants (ChatGPT, Gemini via `WEB_AI_PROVIDERS`) in a persistent Chrome profile, scores the replies by code presence, length and relevance, and returns the best answer to inform building. Logins persist across runs in `web_ai_profile/`.
- `ask_web` tool schema and executor wiring; research phase now instructed to use it for cross-checking answers.
- Tests for the aggregator (offline-safe): best-answer selection, error skipping, scoring, provider filtering.

## [0.4.0] - 2026-08-07

### Added

- **Persistent run history**: every run writes a queryable JSONL timeline (`runs/*.jsonl`) of tool calls, phases, and the final report (`agent/history.py`). The web frontend adds a Run History panel and `/api/history` + `/api/runs/<id>` endpoints to reopen any run's timeline and report.

### Fixed

- Docker sandbox command quoting on Windows: `_run_in_docker` now passes arguments as a list instead of `shell=True`, avoiding POSIX-quote mangling by the Windows shell.

## [0.3.0] - 2026-08-06

### Added

- **Embedding-based RAG**: dense retrieval via OpenAI/Ollama embedding models with automatic TF-IDF fallback (`agent/retrieval.py`).
- **Task-keyed memory**: research notes stored per task under `research_notes/<task-slug>.md`.
- **Streaming LLM output**: `--stream` prints model reasoning live to the console.
- **Sandboxed command execution**: `--sandbox` blocks destructive commands, confines file tools to the working directory, and runs commands in a Docker container when available.
- **Web frontend** (`frontend/`): Flask UI to configure and launch runs and stream output over Server-Sent Events.