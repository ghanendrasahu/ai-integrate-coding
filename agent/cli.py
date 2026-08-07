import argparse
import os
import sys

from dotenv import load_dotenv

from agent import Agent
from agent.config import resolve_config


class Tee:
    def __init__(self, stream, log_file):
        self.stream = stream
        self.file = log_file

    def write(self, data):
        self.stream.write(data)
        self.file.write(data)

    def flush(self):
        self.stream.flush()
        self.file.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autonomous-agent",
        description="Autonomous coding agent: researches with Chrome (RAG), then builds, verifies and upgrades a project to production grade.",
    )
    parser.add_argument("prompt", nargs="+", help="The task description.")
    parser.add_argument("--workdir", default=None, help="Directory where the project is created (default: ./workspace).")
    parser.add_argument("--interactive", action="store_true", help="Allow the agent to ask you questions when blocked.")
    parser.add_argument("--no-browser", action="store_true", help="Disable Chrome research.")
    parser.add_argument("--headless", action="store_true", default=True, help="Run Chrome headless (default).")
    parser.add_argument("--show-browser", action="store_true", help="Run Chrome with a visible window.")
    parser.add_argument("--model", default=None, help="Override the LLM model name.")
    parser.add_argument("--max-steps", type=int, default=None, help="Override steps allowed per phase.")
    parser.add_argument("--review-gates", action="store_true", help="Pause between phases for human approval.")
    parser.add_argument("--stream", action="store_true", help="Stream the model's reasoning live to the console.")
    parser.add_argument("--sandbox", action="store_true", help="Run commands in a sandbox (destructive-command guard, Docker isolation when available).")
    parser.add_argument("--log", default=None, help="Path to the run log file (default: agent_run.log in the workdir).")
    parser.add_argument("--no-log", action="store_true", help="Disable writing the run log file.")
    return parser


def _setup_utf8():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _setup_logging(workdir: str, log_setting: str | None, no_log: bool):
    if no_log or not log_setting:
        return
    log_path = os.path.abspath(log_setting) if os.path.isabs(log_setting) else os.path.join(workdir, log_setting)
    try:
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = Tee(sys.stdout, log_file)
        sys.stderr = Tee(sys.stderr, log_file)
    except OSError:
        pass


def main() -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    cfg = resolve_config(args)
    _setup_utf8()

    task = " ".join(args.prompt)
    workdir = os.path.abspath(args.workdir or os.path.join(os.getcwd(), "workspace"))
    os.makedirs(workdir, exist_ok=True)
    _setup_logging(workdir, cfg.get("log_file") or None, args.no_log)

    agent = Agent(
        task=task,
        workdir=workdir,
        interactive=cfg["interactive"],
        use_browser=cfg["use_browser"],
        headless=cfg["headless"],
        model=cfg.get("model") or None,
        max_steps=cfg["max_steps"],
        review_gates=cfg["review_gates"],
        stream=cfg.get("stream", False),
        sandbox=cfg.get("sandbox", False),
    )

    print(f"Task   : {task}")
    print(f"Workdir: {workdir}")
    print(f"Browser: {'on' if cfg['use_browser'] else 'off'} ({'headless' if cfg['headless'] else 'visible'})")
    print(f"Stream : {'on' if cfg.get('stream', False) else 'off'}")
    print(f"Sandbox: {'on' if cfg.get('sandbox', False) else 'off'}")

    try:
        report = agent.run()
    except KeyboardInterrupt:
        print("\n[AGENT] Interrupted by user.")
        return 130
    except Exception as exc:
        print(f"\n[AGENT] Fatal: {type(exc).__name__}: {exc}")
        return 1

    print("\n================ AGENT FINAL REPORT ================")
    print(report)
    print("====================================================")
    print(f"Project written to: {workdir}")
    return 0
