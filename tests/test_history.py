import json

import agent.agent as agent_module
import pytest
from agent import Agent
from agent.history import RunHistory, _slugify
from tests.fakes import FakeLLM


def test_slugify():
    assert _slugify("Build a Flask API") == "build-a-flask-api"
    assert _slugify("!!!") == "task"
    assert _slugify("a" * 100)[-5:] != "-----"


def test_run_history_records_to_jsonl(tmp_path):
    history = RunHistory(str(tmp_path), "build a todo app")
    history.record("phase", phase="research", summary="done")
    history.record("report", report="all good")
    assert history.path.startswith(str(tmp_path / "runs"))
    lines = open(history.path, encoding="utf-8").read().strip().splitlines()
    events = [json.loads(line) for line in lines]
    assert events[0]["type"] == "meta"
    assert events[0]["task"] == "build a todo app"
    assert events[1]["type"] == "phase"
    assert events[1]["summary"] == "done"
    assert events[2]["type"] == "report"


def test_history_ignores_oserror_on_write(monkeypatch, tmp_path):
    history = RunHistory(str(tmp_path), "hello")

    def fake_open(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", fake_open)
    history.record("phase", phase="build")
    history.record("report", report="x")


def test_agent_records_phases_and_report(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "LLMClient", FakeLLM)
    agent = Agent(task="build a hello app", workdir=str(tmp_path), use_browser=False, max_steps=12)
    agent.run()
    runs_dir = tmp_path / "runs"
    files = list(runs_dir.glob("*.jsonl"))
    assert len(files) == 1
    events = [json.loads(line) for line in open(files[0], encoding="utf-8").read().strip().splitlines()]
    types = [e["type"] for e in events]
    assert "meta" in types
    assert "tool" in types
    assert "phase" in types
    assert types.count("phase") == 4
    assert "report" in types


def test_history_is_persistent_across_agent_instances(tmp_path):
    RunHistory(str(tmp_path), "task").record("phase", phase="x")
    files = list((tmp_path / "runs").glob("*.jsonl"))
    assert len(files) == 1