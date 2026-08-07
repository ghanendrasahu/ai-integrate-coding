# Autonomous AI Coding Agent

[![CI](https://github.com/ghanendrasahu/ai_intigrate_coding/actions/workflows/ci.yml/badge.svg)](https://github.com/ghanendrasahu/ai_intigrate_coding/actions/workflows/ci.yml)
[![CD](https://github.com/ghanendrasahu/ai_intigrate_coding/actions/workflows/cd.yml/badge.svg)](https://github.com/ghanendrasahu/ai_intigrate_coding/actions/workflows/cd.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-66%20passing-brightgreen)](tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A self-driving software engineering agent that turns a single task prompt into a **production-grade project**. It researches the web using real Chrome automation (RAG-style grounding), builds the project from those researched facts, verifies it by running real commands, and keeps upgrading it until it is genuinely production-ready — with no human in the loop.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [CI / CD](#ci--cd)
- [CLI Reference](#cli-reference)
- [Examples](#examples)
- [Web Frontend](#web-frontend)
- [Project Structure](#project-structure)
- [Tool Reference](#tool-reference)
- [How to Extend](#how-to-extend)
- [Verification & Testing](#verification--testing)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Autonomous workflow** — Research → Build → Verify → Upgrade, with no manual steps in between.
- **Chrome as a RAG knowledge base** — the agent asks itself the relevant questions from your prompt, searches the web in a real Chrome browser, reads pages, and stores the findings as persistent research notes that feed every later decision.
- **Semantic research retrieval** — instead of dumping the whole knowledge base into context, only the top-K notes most relevant to the current task and phase are retrieved each turn. Uses dense embeddings (OpenAI `text-embedding-3-small` or Ollama `nomic-embed-text`) when available, with an automatic TF-IDF fallback — so it works with or without an embedding API.
- **Task-keyed memory** — research notes are stored per task under `research_notes/<task-slug>.md`, so separate tasks in the same working directory keep independent knowledge bases that persist across runs.
- **Parallel tool execution** — when the model issues several tool calls in one response (common during research), they run concurrently for faster research, with thread-safe note and browser handling.
- **Streaming LLM output** — `--stream` prints the model's reasoning live to the console instead of only showing tool results.
- **Sandboxed command execution** — `--sandbox` blocks destructive shell commands (denylist) and confines file tools to the working directory; when Docker is available it runs commands inside an isolated container (`AGENT_SANDBOX_IMAGE`).
- **Conversation summarization** — when the conversation hits its message cap, older context is compressed by the LLM into a summary instead of being dropped, preserving decisions across long phases.
- **Persistent run history** — every run writes a queryable JSONL timeline (`runs/*.jsonl`) of tool calls, phases, and the final report; the web frontend lists past runs and lets you reopen any timeline for cross-project planning.
- **Multi-app in-browser AI sourcing** — the `ask_web` tool asks several browser-based AI assistants (ChatGPT, Gemini, and more via `WEB_AI_PROVIDERS`) in a persistent Chrome profile, scores the replies (code quality, length, relevance), and returns the best answer to inform building.
- **Config file + `.env`** — settings load from `agent.toml`, `.env`, and environment variables, with CLI flags taking precedence (see [Configuration](#configuration)).
- **Run log** — every run is teed to `agent_run.log` in the working directory for debugging.
- **Human review gates** — optional checkpoints between phases (`--review-gates`) where you can continue, skip the rest, or abort.
- **CI-ready output** — generated projects are instructed to include a GitHub Actions CI workflow with install/lint/test steps.
- **Installable package** — works as `python main.py`, `python -m agent`, or the installed `autonomous-agent` command.
- **Web frontend** — an optional Flask UI in `frontend/` to configure, launch, and live-stream agent runs over Server-Sent Events.
- **Ground-truth code, not guesses** — versions, APIs, and best practices come from live research instead of the model's memory.
- **Self-verifying** — runs installs, builds, lints, tests, and actually starts the application, reading the full output and fixing every error it finds.
- **Self-upgrading** — critiques its own work (performance, security, correctness, maintainability, tests, deployment) and iterates until the result is production-grade.
- **Provider-agnostic LLM backend** — works with OpenAI, Gemini, any OpenAI-compatible endpoint, or a fully local Ollama server.
- **Graceful degradation** — browser research, interactivity, and shell execution can each be toggled independently.

## How It Works

The agent is an orchestrator that runs four sequential phases. Each phase is a tool-calling loop: the LLM picks a tool, the executor runs it, and the result is fed back — repeated until the phase signals completion.

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  RESEARCH   │ → │   BUILD     │ → │   VERIFY    │ → │   UPGRADE   │
│ Chrome-based│   │ write files │   │ run + fix   │   │ critique +  │
│ Q&A + notes │   │ from notes  │   │ until clean │   │ re-verify   │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

1. **Research** — derives the relevant questions from the task and answers them by searching the web in Chrome. Findings are saved one fact at a time into a persistent knowledge base (`append_note`) that stays available to every later step.
2. **Build** — writes the complete project (source, tests, dependency manifest, configuration) using the researched facts and conventions.
3. **Verify** — installs dependencies, runs the build/lint/type-check/tests, starts the application, and inspects console output and exit codes. Every error found is fixed by editing files, then re-verified.
4. **Upgrade** — self-critiques the implementation against production standards, researches again if needed, upgrades the code, and re-runs verification until the result is production-grade.

## System Requirements

| Requirement | Details |
| --- | --- |
| Operating system | Windows / macOS / Linux |
| Python | **3.11+** (3.10+ should work; 3.11 recommended) |
| Chrome | Google Chrome installed (used by Playwright for research; not needed if using `playwright install chromium`) |
| LLM backend | One of: OpenAI API key, Gemini API key, OpenAI-compatible endpoint, or a local Ollama server |

> **Docker path:** no local Python, Chrome, or Playwright is needed — the [Docker image](#run-with-docker-easiest) bundles all of it.

## Installation

It is strongly recommended to use a virtual environment:

```bash
# Windows (PowerShell)
py -3.11 -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3.11 -m venv .venv
source .venv/bin/activate
```

Then install the dependencies:

```bash
pip install -r requirements.txt
```

Or install the agent as a package (recommended — also gives you the `autonomous-agent` command):

```bash
pip install -e .
```

You can then launch the agent any of these three ways:

```bash
python main.py "..."
python -m agent "..."
autonomous-agent "..."
```

Dependencies:

| Package | Purpose |
| --- | --- |
| `openai` | LLM client (works with OpenAI, Gemini, Ollama, and any OpenAI-compatible API) |
| `playwright` | Chrome automation for web research |
| `python-dotenv` | Loads configuration from a `.env` file |
| `flask` | Web frontend (`frontend/`) |

If Chrome is not available, install Playwright's bundled browser as a fallback:

```bash
playwright install chromium
```

## Configuration

All configuration is provided through environment variables. **No secrets are hardcoded.**

| Variable | Default | Description |
| --- | --- | --- |
| `AGENT_API_KEY` | — | API key for the LLM provider (OpenAI or Gemini). |
| `AGENT_API_BASE` | — | Custom base URL for OpenAI-compatible endpoints. |
| `AGENT_MODEL` | `gpt-4o` | Model name to use. |
| `AGENT_PROVIDER` | *(auto)* | Force a provider: `openai`, `openai-compatible`, or `ollama`. Auto-detected from the surrounding env when left empty. |
| `OLLAMA_BASE` | `http://localhost:11434/v1` | URL of a local Ollama server. |
| `AGENT_EMBED_MODEL` | `text-embedding-3-small` | Embedding model for RAG retrieval (OpenAI) or `nomic-embed-text` (Ollama). |
| `AGENT_SANDBOX_IMAGE` | `python:3.11-slim` | Docker image used for sandboxed command execution. |
| `WEB_AI_PROVIDERS` | `chatgpt,gemini` | Comma-separated browser-based AI assistants queried by the `ask_web` tool. |

### OpenAI

```bash
set AGENT_API_KEY=sk-...
set AGENT_MODEL=gpt-4o
```

### Gemini (via OpenAI-compatible endpoint)

```bash
set AGENT_API_KEY=AIza...
set AGENT_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai/
set AGENT_MODEL=gemini-2.0-flash
```

### Fully local (Ollama)

```bash
set AGENT_PROVIDER=ollama
set AGENT_MODEL=qwen2.5-coder:14b
```

### Using a `.env` file

Instead of setting shell variables every time, create a `.env` file in the project root (start from the `.env.example` template) with the variables from the table above:

```bash
AGENT_API_KEY=sk-...
AGENT_API_BASE=https://api.groq.com/openai/v1
AGENT_MODEL=llama-3.3-70b-versatile
```

Values are loaded automatically on startup. `.env` is gitignored and never committed.

### Using `agent.toml`

For file-based configuration, create an `agent.toml` (gitignored):

```toml
[agent]
interactive = false
use_browser = true
headless = true
max_steps = 40
review_gates = false
stream = false
sandbox = false
log_file = "agent_run.log"

[llm]
model = "gpt-4o"
provider = ""
api_base = ""
```

Precedence (highest wins): **CLI flags > environment variables > `agent.toml` > defaults**. Secrets (API keys) should only live in environment variables or `.env`.

## Usage

### Run with Docker (easiest)

No local Python or Playwright install needed. Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) (already tested with Docker 29.x + Compose v2). Set your API key in `.env` first (see [Configuration](#configuration)).

```bash
# 1. Web frontend (control every run in-browser) at http://localhost:5000
docker compose up --build

# 2. CLI (direct terminal control of a single task)
docker compose run --rm cli "build a Flask REST API for a task tracker with JWT auth"
```

Alternatively, skip the local build and pull the image published by [CD](#ci--cd):

```bash
docker pull ghcr.io/ghanendrasahu/ai_intigrate_coding:latest
docker run -p 5000:5000 --env-file .env ghcr.io/ghanendrasahu/ai_intigrate_coding:latest
```

- Live code is bind-mounted, so edits are picked up without rebuilding — except changes to Python packages or Playwright, which need `docker compose build`.
- Chromium is bundled in the image, so the browser research / web-sourcing tools work out of the box.
- The optional `--sandbox` Docker isolation needs the host Docker socket exposed (see the commented lines in `docker-compose.yml`). Only enable it if you trust the tasks you run.

### Command shortcuts

On **Windows PowerShell** (no `make` needed), use the included `make.ps1`, which mirrors the Makefile:

```powershell
.\make.ps1 up                    # start the web frontend at http://localhost:5000
.\make.ps1 cli "build a REST API"     # run one task via the containerized agent
.\make.ps1 logs                  # tail the frontend logs
.\make.ps1 down                  # stop everything
.\make.ps1 setup / test / lint / clean   # local (non-Docker) workflows
```

On **Git Bash / WSL / Linux / macOS** the `Makefile` provides the same targets:

```bash
make up                    # start the web frontend at http://localhost:5000
make cli TASK="build a REST API"   # run one task via the containerized agent
make logs                  # tail the frontend logs
make down                  # stop everything

# Local (non-Docker) workflows
make setup                 # .venv + deps + Playwright Chromium
make test                  # full test suite
make lint                  # pyright type-check
make clean                 # remove Python caches
```

Both `test`/`lint` auto-use `.venv/Scripts/python` when present.

### Quick start (local, without Docker)

```bash
pip install -r requirements.txt
python -m playwright install chromium
python main.py "build a Flask REST API for a task tracker with JWT auth and tests"
```

The agent prints a live log of every action it takes, and finishes with a final report summarizing each phase. The generated project is written to `./workspace/` by default.

### Typical flags

```bash
# Write the project to a specific directory
python main.py --workdir C:\path\to\project "build a CLI password manager"

# Let the agent ask you questions when it is truly blocked
python main.py --interactive "build a chatbot with streaming responses"

# Pause between phases for human approval
python main.py --review-gates "build an e-commerce API"

# Watch Chrome research in a visible window
python main.py --show-browser "build a web scraper for product prices"

# No browser research at all (relies on the model's own knowledge)
python main.py --no-browser "write a python script that parses CSV files"

# Point the run log somewhere specific, or disable it
python main.py --log run.log "..."
python main.py --no-log "..."

# Stream the model's reasoning live to the console
python main.py --stream "build a cli todo app"

# Sandbox command execution (denylist + Docker isolation when available)
python main.py --sandbox "build a web scraper"
```

## CI / CD

The repository ships two GitHub Actions workflows. Both run on every relevant event automatically and have been verified end-to-end on the live repo.

| Workflow | Trigger | What it does |
| --- | --- | --- |
| **CI** (`.github/workflows/ci.yml`) | every push / PR to `main` | Installs deps + Chromium, runs the full test suite, and builds the Docker image. |
| **CD** (`.github/workflows/cd.yml`) | every `v*` tag | Builds the image and publishes it to **GitHub Container Registry** as both `<tag>` and `latest`. |

```bash
# Pull the ready-to-run image published by CD (no build needed)
docker pull ghcr.io/ghanendrasahu/ai_intigrate_coding:latest
docker run -p 5000:5000 --env-file .env ghcr.io/ghanendrasahu/ai_intigrate_coding:latest
```

The GHCR image is **private** while the repository is private (pull with a token that has `read:packages`). If the repo is made public, the package can be made public too.

## CLI Reference

```
usage: autonomous-agent [-h] [--workdir WORKDIR] [--interactive] [--no-browser]
                        [--headless] [--show-browser] [--model MODEL]
                        [--max-steps MAX_STEPS] [--review-gates] [--stream]
                        [--sandbox] [--log LOG] [--no-log]
                        prompt [prompt ...]
```

| Argument | Default | Description |
| --- | --- | --- |
| `prompt` | — | The task description (required). |
| `--workdir PATH` | `./workspace` | Directory where the project is created. |
| `--interactive` | off | Allow the agent to ask you questions when blocked. |
| `--no-browser` | off | Disable Chrome research entirely. |
| `--headless` | on | Run Chrome headless (no window). |
| `--show-browser` | off | Run Chrome with a visible window. |
| `--model NAME` | env | Override the LLM model for this run. |
| `--max-steps N` | `40` | Override the maximum tool steps allowed per phase. |
| `--review-gates` | off | Pause between phases and ask for approval (continue/skip/abort). |
| `--stream` | off | Stream the model's reasoning live to the console. |
| `--sandbox` | off | Sandbox command execution (destructive-command denylist, Docker isolation when available). |
| `--log PATH` | `agent_run.log` | Write the run log to this file (relative to the workdir). |
| `--no-log` | off | Do not write a run log file. |

## Examples

**Build a Flask API:**
```bash
python main.py "build a Flask REST API for a task tracker with JWT auth, SQLite storage, and a test suite"
```

**Fix and productionize an existing folder:**
```bash
python main.py --workdir C:\Users\me\projects\my-app "audit this project, fix all bugs, and upgrade it to production quality"
```

**Build a small data-science tool:**
```bash
python main.py "build a python script that downloads stock prices and generates a matplotlib report, with unit tests"
```

## Web Frontend

An optional Flask web UI (`frontend/`) lets you configure and launch the agent from a browser and watch its output live.

```bash
cd frontend
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000, enter a task, pick options (working directory, model, browser, streaming, sandbox, interactive), and press **Launch agent**. The run streams over Server-Sent Events and the captured output is shown as the final report.

Configurable via environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `FLASK_HOST` | `127.0.0.1` | Interface the frontend binds to. |
| `FLASK_PORT` | `5000` | Port the frontend listens on. |
| `FLASK_DEBUG` | *(off)* | Set to `1` to enable Flask debug mode. |

The agent subprocess runs from the repository root, so it uses the same `.env` / `agent.toml` and LLM backend as the CLI. Completed runs are recorded under `<workdir>/runs/*.jsonl` and appear in the **Run history** panel, where you can reopen any run's timeline and final report.

### Browser-based AI assistants (`ask_web`)

To let the agent draw on ChatGPT, Gemini, and other web apps from Chrome, log into those services once in the shared profile it manages. Run a first headful session so the sessions persist:

```bash
cd frontend
python app.py
# launch once with the browser visible, sign into chatgpt.com and gemini.google.com,
# then the persisted web_ai_profile is reused across all runs.
```

Tune which services are queried with `WEB_AI_PROVIDERS` (e.g. `WEB_AI_PROVIDERS=chatgpt,gemini`). The `ask_web` tool asks each, picks the best reply by a code/relevance/length score, and feeds it to the research phase.

## Project Structure

```
.
├── main.py                  Thin CLI wrapper
├── requirements.txt         Runtime dependencies
├── requirements-dev.txt     Development dependencies (pytest, pyright)
├── pyproject.toml           Packaging + tool configuration (pytest, pyright)
├── CHANGELOG.md             Release history
├── Dockerfile               Single image: agent + frontend + Chromium, Flask included
├── docker-compose.yml       `web` (frontend) + `cli` services, live code-mount
├── Makefile                 Make shortcuts (up / cli / test / lint / clean) for Git Bash, WSL, macOS, Linux
├── make.ps1                 Same shortcuts for Windows PowerShell (no `make` needed)
├── .dockerignore            Files excluded from the image build
├── .github/workflows/ci.yml CI: tests + Docker build on push / PR
├── .github/workflows/cd.yml CD: publish image to GHCR on `v*` tags
├── .env.example              Config template (copy to `.env` and fill in)
├── LICENSE                   MIT License
├── .gitignore
├── agent/
│   ├── __init__.py          Package exports
│   ├── __main__.py          `python -m agent` entry point
│   ├── agent.py             Orchestrator: research → build → verify → upgrade loop
│   ├── browser.py           Chrome automation for web search and page extraction (RAG)
│   ├── cli.py               CLI parsing, config merging, run-log tee
│   ├── config.py            agent.toml / env / CLI configuration resolution
│   ├── history.py           JSONL run-history timeline recorder
│   ├── llm.py               Provider-agnostic LLM client with tool calling
│   ├── retrieval.py         RAG retriever: dense embeddings (OpenAI/Ollama) with TF-IDF fallback
│   ├── weblm.py             Multi-app in-browser AI aggregator (ChatGPT/Gemini, best-answer scoring)
│   └── tools.py             Tool schemas and executor (web, file, shell, notes, finish, sandbox)
├── frontend/
│   ├── app.py               Flask web UI: configure, launch, and live-stream agent runs (SSE)
│   ├── requirements.txt     Frontend runtime deps (Flask, etc.)
│   ├── templates/index.html Browser UI for launching and monitoring a run
│   ├── tests/test_app.py    Frontend API and streaming tests
│   └── README.md            Frontend setup and usage
└── tests/
    ├── fakes.py             Scripted fake LLM used to test the phase loop offline
    ├── test_agent.py        End-to-end phase loop tests (no API key needed)
    ├── test_browser.py      Chrome/Playwright search and extraction tests
    ├── test_cli.py          CLI flags, run-log and report output
    ├── test_config.py       Configuration precedence tests
    ├── test_history.py      Run-history timeline tests
    ├── test_retrieval.py    Knowledge-base retriever tests
    ├── test_tools.py        Tool executor tests (files, shell, notes persistence)
    └── test_weblm.py        Web AI aggregator tests
```

## Tool Reference

The LLM can call the following tools during any phase:

| Tool | Description |
| --- | --- |
| `web_search` | Search the web using Chrome; returns titles, URLs, and snippets. |
| `web_open` | Open a specific URL in Chrome and return its readable text. |
| `ask_web` | Ask multiple browser-based AI assistants (ChatGPT, Gemini, ...) and return the best answer. |
| `append_note` | Save one research finding into the persistent knowledge base (RAG notes), keyed by task. |
| `list_dir` | List files in a directory. |
| `read_file` | Read a text file. |
| `write_file` | Create or overwrite a file (UTF-8, parent dirs auto-created). |
| `run_command` | Run a shell command and return exit code, stdout, and stderr. |
| `ask_user` | Ask the human a question (only active with `--interactive`). |
| `finish` | Signal that the current phase is complete. |

## How to Extend

### Add a new tool

1. Add a JSON schema to `TOOL_SCHEMAS` in `agent/tools.py`.
2. Implement the handler as `_exec_<tool_name>(self, args: dict) -> str`.
3. The agent picks it up automatically — no wiring required.

### Add a new phase

1. Add the phase instructions to the `PHASES` dict in `agent/agent.py`.
2. Add the phase name to the sequence tuple in `Agent.run()`.

### Add a configuration option

1. Add the default to `resolve_config()` in `agent/config.py`.
2. Expose it as a CLI flag in `agent/cli.py` if it should be overridable per run.

## Verification & Testing

Install the dev dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
python -m pytest
```

> The suite includes an offline end-to-end test of the phase loop using a scripted fake LLM — no API key or Chrome needed. Browser tests are skipped automatically if Chrome or the network is unavailable.

Static type checking (matches Pylance):

```bash
pyright main.py agent tests
```

Syntax check:

```bash
python -m py_compile main.py agent\*.py
```

Current status: **66 tests passing** (58 core + 8 frontend), **0 type errors / 0 warnings**.

## Troubleshooting

| Problem | Solution |
| --- | --- |
| `No LLM backend configured` | Set `AGENT_API_KEY`, add it to `.env`, or set `AGENT_PROVIDER=ollama` with Ollama running. |
| `playwright` / `openai` import not resolved in the editor | Install `requirements.txt` in the interpreter your editor uses. |
| `rm` / `del` destructive flags | Blocked by the sandbox denylist. |
| `Executable doesn't exist` / Chrome launch failure | Install Chrome, or run `playwright install chromium` for the fallback browser. |
| `Ask the user is disabled` | Run with `--interactive`. |
| Review gates paused | Type Enter to continue, `s` to skip the remaining phases, or `a` to abort. |
| Garbled Unicode in the console | The agent forces UTF-8 output; ensure your terminal supports UTF-8 (Windows Terminal recommended). |
| Can't pull the GHCR image | The package is private while the repo is private. Authenticate with `docker login ghcr.io` using a token that has `read:packages`, or make the package public (and the repo public if desired). |

## Roadmap

The following are planned or under consideration:

- **Multi-agent orchestration** — split a large task across specialized sub-agents (researcher, builder, verifier).
- **Rerankers & hybrid search** — combine dense + sparse retrieval with a cross-encoder reranker for even stronger recall.
- **Cache-aware builds** — reuse previously fetched web content and LLM responses to cut cost and latency.

## Contributing

Contributions are welcome. Please:

1. Fork the repository and create a feature branch.
2. Keep changes minimal and focused.
3. Run `pyright main.py agent` and the smoke checks before submitting.
4. Open a pull request describing the change and why it is needed.

## License

Released under the [MIT License](LICENSE) — Copyright (c) 2026 ghanendrasahu. You are free to use, modify, and distribute the code with attribution.
