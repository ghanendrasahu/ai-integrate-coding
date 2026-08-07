# Autonomous AI Coding Agent — Web Frontend

A small Flask web UI that configures, launches, and monitors the autonomous coding agent in the parent repository.

## Features

- Configure a run: task prompt, working directory, model, max steps, and toggles for browser research, streaming, sandboxing, and interactive mode.
- Launch the agent as a subprocess (`python -m agent ...`) and watch its live output streamed over Server-Sent Events.
- View the captured run output as the final report.

## Run it

```bash
cd frontend
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

The agent runs from the repository root (`REPO_ROOT`), so it uses the repo's `.env` / `agent.toml` configuration and needs the same LLM backend (Groq/OpenAI/Ollama) to be configured.

## Test

```bash
cd frontend
python -m pytest -q
```
