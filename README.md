# Autonomous AI Coding Agent

A self-driving software engineering agent that turns a single task prompt into a **production-grade project**. It researches the web using real Chrome automation (RAG-style grounding), builds the project from those researched facts, verifies it by running real commands, and keeps upgrading it until it is genuinely production-ready — with no human in the loop.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [CLI Reference](#cli-reference)
- [Examples](#examples)
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
- **Config file + `.env`** — settings load from `agent.toml`, `.env`, and environment variables, with CLI flags taking precedence (see [Configuration](#configuration)).
- **Run log** — every run is teed to `agent_run.log` in the working directory for debugging.
- **Human review gates** — optional checkpoints between phases (`--review-gates`) where you can continue, skip the rest, or abort.
- **CI-ready output** — generated projects are instructed to include a GitHub Actions CI workflow with install/lint/test steps.
- **Installable package** — works as `python main.py`, `python -m agent`, or the installed `autonomous-agent` command.
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
| Chrome | Google Chrome installed (used by Playwright for research) |
| LLM backend | One of: OpenAI API key, Gemini API key, OpenAI-compatible endpoint, or a local Ollama server |

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
| `AGENT_PROVIDER` | *(auto)* | Set to `ollama` to force the local Ollama backend. Auto-detected when no key is configured. |
| `OLLAMA_BASE` | `http://localhost:11434/v1` | URL of a local Ollama server. |
| `AGENT_EMBED_MODEL` | `text-embedding-3-small` | Embedding model for RAG retrieval (OpenAI) or `nomic-embed-text` (Ollama). |
| `AGENT_SANDBOX_IMAGE` | `python:3.11-slim` | Docker image used for sandboxed command execution. |

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

Instead of setting shell variables every time, copy `.env.example` to `.env` and fill it in. Values are loaded automatically on startup:

```bash
copy .env.example .env
# edit .env, then just run the agent
python main.py "..."
```

> `.env` is gitignored and never committed. Only `.env.example` (the template) is tracked.

### Using `agent.toml`

Copy `agent.toml.example` to `agent.toml` for file-based configuration:

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

### Quick start

```bash
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

## Project Structure

```
.
├── main.py                  Thin CLI wrapper
├── requirements.txt         Runtime dependencies
├── requirements-dev.txt     Development dependencies (pytest, pyright)
├── pyproject.toml           Packaging + tool configuration (pytest, pyright)
├── .env.example             Environment variable template
├── agent.toml.example       File-based configuration template
├── .gitignore
├── .vscode/settings.json    Local editor settings (not committed)
├── agent/
│   ├── __init__.py          Package exports
│   ├── __main__.py          `python -m agent` entry point
│   ├── agent.py             Orchestrator: research → build → verify → upgrade loop
│   ├── browser.py           Chrome automation for web search and page extraction (RAG)
│   ├── cli.py               CLI parsing, config merging, run-log tee
│   ├── config.py            agent.toml / env / CLI configuration resolution
│   ├── llm.py               Provider-agnostic LLM client with tool calling
│   ├── retrieval.py         RAG retriever: dense embeddings (OpenAI/Ollama) with TF-IDF fallback
│   └── tools.py             Tool schemas and executor (web, file, shell, notes, finish, sandbox)
└── tests/
    ├── fakes.py             Scripted fake LLM used to test the phase loop offline
    ├── test_agent.py        End-to-end phase loop tests (no API key needed)
    ├── test_browser.py      Chrome/Playwright search and extraction tests
    ├── test_cli.py          CLI flags, run-log and report output
    ├── test_config.py       Configuration precedence tests
    ├── test_retrieval.py    Knowledge-base retriever tests
    └── test_tools.py        Tool executor tests (files, shell, notes persistence)
```

## Tool Reference

The LLM can call the following tools during any phase:

| Tool | Description |
| --- | --- |
| `web_search` | Search the web using Chrome; returns titles, URLs, and snippets. |
| `web_open` | Open a specific URL in Chrome and return its readable text. |
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

Current status: **44 tests passing**, **0 type errors / 0 warnings**.

## Troubleshooting

| Problem | Solution |
| --- | --- |
| `No LLM backend configured` | Set `AGENT_API_KEY`, add it to `.env`, or set `AGENT_PROVIDER=ollama` with Ollama running. |
| `playwright` / `openai` import not resolved in the editor | Install `requirements.txt` in the interpreter your editor uses, or point Pylance at it via `.vscode/settings.json`. |
| `rm` / `del` destructive flags | Blocked by the sandbox denylist. |
| `Executable doesn't exist` / Chrome launch failure | Install Chrome, or run `playwright install chromium` for the fallback browser. |
| `Ask the user is disabled` | Run with `--interactive`. |
| Review gates paused | Type Enter to continue, `s` to skip the remaining phases, or `a` to abort. |
| Garbled Unicode in the console | The agent forces UTF-8 output; ensure your terminal supports UTF-8 (Windows Terminal recommended). |

## Roadmap

The following are planned or under consideration:

- **Persistent run history** — store every phase's decisions in a queryable timeline to support cross-project planning.
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

Private project — all rights reserved.
