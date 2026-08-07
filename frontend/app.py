import json
import os
import queue
import subprocess
import sys
import threading
import uuid

from flask import Flask, Response, jsonify, render_template, request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

RUNS: dict[str, "Run"] = {}
RUNS_LOCK = threading.Lock()


def _clean(value) -> str:
    return str(value).strip() if value else ""


class Run:
    def __init__(self, run_id: str, task: str, workdir: str, args: dict):
        self.run_id = run_id
        self.task = task
        self.workdir = workdir
        self.args = args
        self.process: subprocess.Popen | None = None
        self.lines: queue.Queue = queue.Queue()
        self.done = False


def _build_argv(task: str, workdir: str, opts: dict) -> list[str]:
    argv = [sys.executable, "-m", "agent", task]
    if workdir:
        argv += ["--workdir", workdir]
    if opts.get("no_browser"):
        argv.append("--no-browser")
    if opts.get("interactive"):
        argv.append("--interactive")
    if opts.get("stream"):
        argv.append("--stream")
    if opts.get("sandbox"):
        argv.append("--sandbox")
    if opts.get("model"):
        argv += ["--model", opts["model"]]
    if opts.get("max_steps"):
        argv += ["--max-steps", str(opts["max_steps"])]
    return argv


def _pump(run: Run) -> None:
    process = run.process
    stdout = process.stdout if process is not None else None
    if stdout is not None:
        try:
            for line in iter(stdout.readline, ""):
                run.lines.put(("line", line))
        except AttributeError:
            pass
        finally:
            if process is not None:
                process.wait()
    run.lines.put(("done", ""))
    run.done = True


def _launch(run: Run) -> None:
    argv = _build_argv(run.task, run.workdir, run.args)
    run.process = subprocess.Popen(
        argv,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    threading.Thread(target=_pump, args=(run,), daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/launch", methods=["POST"])
def launch():
    data = request.get_json(force=True, silent=True) or {}
    task = _clean(data.get("task"))
    if not task:
        return jsonify({"error": "task is required"}), 400
    run_id = uuid.uuid4().hex[:12]
    run = Run(
        run_id=run_id,
        task=task,
        workdir=_clean(data.get("workdir")),
        args={
            "no_browser": bool(data.get("no_browser")),
            "interactive": bool(data.get("interactive")),
            "stream": bool(data.get("stream")),
            "sandbox": bool(data.get("sandbox")),
            "model": _clean(data.get("model")),
            "max_steps": int(data.get("max_steps") or 0) or None,
        },
    )
    with RUNS_LOCK:
        RUNS[run_id] = run
    try:
        _launch(run)
    except Exception as exc:
        with RUNS_LOCK:
            RUNS.pop(run_id, None)
        return jsonify({"error": f"failed to launch agent: {exc}"}), 500
    return jsonify({"run_id": run_id})


@app.route("/api/runs/<run_id>/stream")
def stream(run_id: str):
    run = RUNS.get(run_id)
    if run is None:
        return jsonify({"error": "unknown run"}), 404

    def generate():
        yield f"data: {json.dumps({'type': 'meta', 'run_id': run_id, 'task': run.task, 'workdir': run.workdir})}\n\n"
        while True:
            try:
                kind, payload = run.lines.get(timeout=15)
            except queue.Empty:
                if run.done:
                    break
                yield ": keepalive\n\n"
                continue
            if kind == "line":
                yield f"data: {json.dumps({'type': 'line', 'text': payload})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG") == "1",
        use_reloader=False,
    )
