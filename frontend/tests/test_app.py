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
