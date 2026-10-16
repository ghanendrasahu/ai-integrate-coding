import hmac
import json
import os
import queue
import subprocess
import sys
import threading
import uuid

from flask import Flask, Response, jsonify, render_template, request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.path.join(REPO_ROOT, "workspace", "runs")

# Runs launched from the web UI always execute inside this root, with the
# sandbox enabled and a hard step cap. They never touch the repository itself.
WORKSPACE_ROOT = os.path.realpath(
    os.environ.get(
        "AGENT_WORKSPACE_ROOT", os.path.join(REPO_ROOT, "workspace", "projects")
    )
)
ACCESS_TOKEN = os.environ.get("UI_ACCESS_TOKEN", "").strip()
ALLOW_PUBLIC_LAUNCH = os.environ.get("ALLOW_PUBLIC_LAUNCH", "").strip().lower() in {
    "1",
    "true",
    "yes",
}
MAX_WEB_STEPS = max(1, min(int(os.environ.get("MAX_WEB_STEPS", "20")), 60))
PUBLIC_API_PATHS = {"/api/health"}

app = Flask(__name__)

RUNS: dict[str, "Run"] = {}
RUNS_LOCK = threading.Lock()


def _provided_token() -> str:
    """Token from the header, or the query string for EventSource requests."""
    return (
        request.headers.get("X-Access-Token") or request.args.get("token", "")
    ).strip()


@app.before_request
def _guard_api():
    """Require UI_ACCESS_TOKEN for the API when one is configured."""
    if not request.path.startswith("/api/") or request.path in PUBLIC_API_PATHS:
        return None
    if ACCESS_TOKEN and not hmac.compare_digest(_provided_token(), ACCESS_TOKEN):
        return jsonify({"error": "Unauthorized. Provide the access token."}), 401
    return None


@app.after_request
def _security_headers(response):
    """Apply the fleet's baseline security headers to every response."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
    )
    return response


def _safe_workdir(requested: str, run_id: str) -> str:
    """Resolve a web request to a directory inside WORKSPACE_ROOT only."""
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)
    if not requested:
        target = os.path.join(WORKSPACE_ROOT, f"run-{run_id}")
    else:
        target = (
            requested
            if os.path.isabs(requested)
            else os.path.join(WORKSPACE_ROOT, requested)
        )
    target = os.path.realpath(target)
    if os.path.commonpath([target, WORKSPACE_ROOT]) != WORKSPACE_ROOT:
        raise ValueError("workdir must stay inside the agent workspace")
    os.makedirs(target, exist_ok=True)
    return target


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
        self.output: list[str] = []
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
                run.output.append(line)
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


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


def _load_run(run_id: str) -> list[dict] | None:
    path = os.path.join(RUNS_DIR, f"{run_id}.jsonl")
    if not os.path.exists(path):
        return None
    events: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    events.append(json.loads(line))
    except OSError:
        return None
    return events


@app.route("/api/history")
def history():
    runs: list[dict] = []
    if os.path.isdir(RUNS_DIR):
        for name in sorted(os.listdir(RUNS_DIR), reverse=True):
            if not name.endswith(".jsonl"):
                continue
            run_id = name[: -len(".jsonl")]
            events = _load_run(run_id)
            if not events:
                continue
            meta = next((e for e in events if e.get("type") == "meta"), {})
            phases = [e.get("phase") for e in events if e.get("type") == "phase"]
            started = events[0].get("ts") if events else None
            last = events[-1].get("ts") if events else None
            runs.append(
                {
                    "run_id": run_id,
                    "task": meta.get("task", run_id),
                    "started": started,
                    "finished": last,
                    "phases": phases,
                    "has_report": any(e.get("type") == "report" for e in events),
                }
            )
    return jsonify({"runs": runs})


@app.route("/api/runs/<run_id>")
def run_detail(run_id: str):
    events = _load_run(run_id)
    if events is not None:
        return jsonify({"run_id": run_id, "events": events})
    # A just-launched run is live in memory until the agent writes its
    # timestamped history file, so resolve its buffered output here instead
    # of returning 404 for an id that /api/launch just handed out.
    run = RUNS.get(run_id)
    if run is not None:
        return jsonify(
            {
                "run_id": run_id,
                "task": run.task,
                "workdir": run.workdir,
                "done": run.done,
                "events": [{"type": "line", "text": line} for line in list(run.output)],
            }
        )
    return jsonify({"error": "unknown run"}), 404


@app.route("/api/launch", methods=["POST"])
def launch():
    if not ACCESS_TOKEN and not ALLOW_PUBLIC_LAUNCH:
        return (
            jsonify(
                {
                    "error": "Launching is disabled. Set UI_ACCESS_TOKEN to enable "
                    "authenticated runs (or ALLOW_PUBLIC_LAUNCH=1 for a trusted local demo)."
                }
            ),
            403,
        )
    data = request.get_json(force=True, silent=True) or {}
    task = _clean(data.get("task"))
    if not task:
        return jsonify({"error": "task is required"}), 400
    if len(task) > 8000:
        return jsonify({"error": "task is too long (limit 8000 characters)"}), 400
    run_id = uuid.uuid4().hex[:12]
    try:
        workdir = _safe_workdir(_clean(data.get("workdir")), run_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        requested_steps = int(data.get("max_steps") or MAX_WEB_STEPS)
    except (TypeError, ValueError):
        return jsonify({"error": "max_steps must be a number"}), 400
    run = Run(
        run_id=run_id,
        task=task,
        workdir=workdir,
        args={
            "no_browser": bool(data.get("no_browser")),
            "interactive": False,  # no terminal is attached to a web run
            "stream": bool(data.get("stream")),
            # Never trust the form here: web runs are always sandboxed.
            "sandbox": True,
            "model": _clean(data.get("model")),
            "max_steps": max(1, min(requested_steps, MAX_WEB_STEPS)),
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
