import pytest

import app as frontend


@pytest.fixture
def client():
    frontend.app.config["TESTING"] = True
    with frontend.app.test_client() as client:
        yield client


@pytest.fixture
def clean_runs(monkeypatch):
    monkeypatch.setattr(frontend, "RUNS", {})
    return frontend.RUNS


def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Autonomous AI Coding Agent" in body
    assert "Launch" in body


def test_launch_requires_task(client):
    response = client.post("/api/launch", json={})
    assert response.status_code == 400
    assert "task" in response.get_json()["error"]


def test_build_argv():
    argv = frontend._build_argv(
        "build a todo app",
        "C:/work",
        {
            "no_browser": True,
            "interactive": False,
            "stream": True,
            "sandbox": True,
            "model": "llama-3.3-70b-versatile",
            "max_steps": 12,
        },
    )
    assert argv[0:2] == ["python", "-m"] or argv[1:3] == ["-m", "agent"]
    assert "build a todo app" in argv
    assert "--workdir" in argv and "C:/work" in argv
    assert "--no-browser" in argv
    assert "--stream" in argv
    assert "--sandbox" in argv
    assert "--model" in argv
    assert "--max-steps" in argv and "12" in argv


def test_launch_creates_run_and_streams(monkeypatch, client, clean_runs):
    def fake_launch(run):
        run.lines.put(("line", "=== PHASE: RESEARCH ===\n"))
        run.lines.put(("done", ""))

    monkeypatch.setattr(frontend, "_launch", fake_launch)
    response = client.post(
        "/api/launch",
        json={"task": "hello", "stream": True, "sandbox": False, "no_browser": True},
    )
    assert response.status_code == 200
    run_id = response.get_json()["run_id"]
    run = clean_runs[run_id]
    assert run.task == "hello"
    assert run.args["stream"] is True
    assert run.args["sandbox"] is False

    stream = client.get(f"/api/runs/{run_id}/stream")
    assert stream.status_code == 200
    assert stream.mimetype == "text/event-stream"
    body = stream.get_data(as_text=True)
    assert "PHASE: RESEARCH" in body
    assert "type\": \"done" in body


def test_stream_unknown_run(client):
    response = client.get("/api/runs/nope/stream")
    assert response.status_code == 404


def _write_run(runs_dir, run_id, events):
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / f"{run_id}.jsonl").write_text(
        "\n".join(__import__("json").dumps(e) for e in events) + "\n",
        encoding="utf-8",
    )


def test_history_lists_runs(monkeypatch, client, tmp_path):
    import json

    import app as frontend

    monkeypatch.setattr(frontend, "RUNS_DIR", str(tmp_path))
    _write_run(
        tmp_path,
        "1700000000_build-a-todo-app",
        [
            {"ts": 1.0, "type": "meta", "task": "build a todo app", "workdir": ""},
            {"ts": 2.0, "type": "phase", "phase": "research", "summary": "ok"},
            {"ts": 3.0, "type": "phase", "phase": "build", "summary": "ok"},
            {"ts": 4.0, "type": "report", "report": "done"},
        ],
    )
    response = client.get("/api/history")
    assert response.status_code == 200
    runs = response.get_json()["runs"]
    assert len(runs) == 1
    assert runs[0]["task"] == "build a todo app"
    assert runs[0]["phases"] == ["research", "build"]
    assert runs[0]["has_report"] is True


def test_run_detail(monkeypatch, client, tmp_path):
    import json

    import app as frontend

    monkeypatch.setattr(frontend, "RUNS_DIR", str(tmp_path))
    _write_run(tmp_path, "abc", [{"ts": 1.0, "type": "meta", "task": "hi"}])
    response = client.get("/api/runs/abc")
    assert response.status_code == 200
    assert response.get_json()["events"][0]["task"] == "hi"


def test_run_detail_unknown(monkeypatch, client, tmp_path):
    import app as frontend

    monkeypatch.setattr(frontend, "RUNS_DIR", str(tmp_path))
    response = client.get("/api/runs/missing")
    assert response.status_code == 404
