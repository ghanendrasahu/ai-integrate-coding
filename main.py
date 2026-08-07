import argparse
import os
import sys

from dotenv import load_dotenv

from agent import Agent


def main() -> int:
    load_dotenv()
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
    parser = argparse.ArgumentParser(
        prog="autonomous-agent",
        description="Autonomous coding agent: researches with Chrome (RAG), then builds, verifies and upgrades a project to production grade.",
    )
    parser.add_argument("prompt", nargs="+", help="The task description.")
    parser.add_argument("--workdir", default=None, help="Directory where the project is created (default: ./workspace).")
    parser.add_argument("--interactive", action="store_true", help="Allow the agent to ask you questions when blocked.")
    parser.add_argument("--no-browser", action="store_true", help="Disable browser research (agent relies on its own knowledge).")
    parser.add_argument("--headless", action="store_true", default=True, help="Run Chrome headless (default).")
    parser.add_argument("--show-browser", action="store_true", help="Run Chrome with a visible window.")
    parser.add_argument("--model", default=None, help="Override the model name (e.g. gpt-4o, gemini-2.0-flash).")
    parser.add_argument("--max-steps", type=int, default=None, help="Override steps allowed per phase.")
    args = parser.parse_args()

    task = " ".join(args.prompt)
    workdir = os.path.abspath(args.workdir or os.path.join(os.getcwd(), "workspace"))
    headless = not args.show_browser

    agent = Agent(
        task=task,
        workdir=workdir,
        interactive=args.interactive,
        use_browser=not args.no_browser,
        headless=headless,
        model=args.model,
        max_steps=args.max_steps,
    )

    print(f"Task   : {task}")
    print(f"Workdir: {workdir}")
    print(f"Browser: {'on' if not args.no_browser else 'off'} ({'headless' if headless else 'visible'})")

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


if __name__ == "__main__":
    sys.exit(main())
