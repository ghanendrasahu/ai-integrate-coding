# Changelog

All notable changes to this project are documented here. Released versions correspond to git tags.

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