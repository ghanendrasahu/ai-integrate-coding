import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from .history import RunHistory
from .llm import LLMClient
from .retrieval import RetrieverProtocol, build_retriever
from .tools import TOOL_SCHEMAS, ToolExecutor

SYSTEM_BASE = """You are an autonomous production-grade software engineering agent.

WORKING DIRECTORY: {workdir}
TASK: {task}

You must complete the task by going through research, build, verification and upgrade
phases until the project is production-ready. You are called phase by phase; when a phase
is complete you call the `finish` tool. The orchestrator then advances you to the next phase.

GENERAL RULES:
- Research FIRST. Break the task into the key relevant questions (correct libraries, current
  stable versions, exact APIs, security and configuration best practices, common pitfalls).
  Use web_search and web_open (Chrome) to answer them and save every finding with append_note.
  These notes form your knowledge base and persist across all phases.
- Write clean production-grade code: correct error handling, type hints, tests, external config
  via environment variables, sensible project layout, no hardcoded secrets.
- Use run_command to install dependencies, lint, test, build and start the application. Always
  read the FULL output and fix every error you find. Iterate until everything passes cleanly.
- Never invent a library, version or API from memory when research can confirm it.
- Only use ask_user when truly blocked (missing secret or genuinely ambiguous requirement).
  Prefer a reasonable, well-documented decision instead.
- Keep messages efficient: read files only as needed, prefer targeted edits.
- For generated projects, include a CI workflow (.github/workflows/ci.yml) whenever the stack
  supports it (Python/Node/etc.), with dependency install, lint/type-check and test steps.

KNOWLEDGE BASE (research notes):
{notes}
"""

PHASES = {
    "research": """PHASE: RESEARCH

Derive the list of relevant questions from the task and answer them by researching the web
with Chrome (web_search / web_open). Also cross-check answers by asking multiple browser-based
AI assistants (ChatGPT, Gemini, etc.) with the ask_web tool and prefer the best answer it returns.
Cover at minimum: correct frameworks/libraries, current
stable versions, exact APIs and code signatures, project structure conventions, security and
configuration best practices, and known pitfalls.

Save one fact per append_note call and cite the source URL in the note. When your notes are
sufficient to design and build the whole project, call finish with a summary of your findings
and the concrete build plan.""",
    "build": """PHASE: BUILD

Using your research notes, create the complete project in the working directory. Write all
files with write_file: source code, tests, dependency manifest (requirements.txt /
package.json / etc.), and any configuration. Follow the conventions your research established.

Use production-grade practices throughout. After writing the files, call finish describing
what you built and listing the verification steps you will run next.""",
    "verify": """PHASE: VERIFY

1. Install dependencies if not already installed.
2. Run the build/lint/type-check/tests (whatever applies).
3. Start the application and check for runtime errors, console output and network failures.
Read the FULL output of every command. Fix each error you find by editing files, then re-run
until everything passes cleanly and the application works as intended.

When verification is clean, call finish with the verification report: commands run, results,
and how the application is started.""",
    "upgrade": """PHASE: UPGRADE

Ask yourself relevant critique questions about the current implementation: correctness,
performance, security, maintainability, error handling, edge cases, tests coverage, UX and
deployment readiness. Compare against your research notes and industry best practices.

Then upgrade the code accordingly (this may include refactoring, adding tests, hardening,
configuration, packaging, and documentation). Re-run verification after each round of upgrades.
Research again if you need more information. Continue until the project is genuinely
production-grade.

When you are confident it is production-ready, call finish with the final report: what was
built, how it was verified, and exactly how to run it.""",
}

MAX_MESSAGES = 60
MAX_RETRIES = 3
MAX_PARALLEL = 4
RETRIEVAL_K = 8
RECENT_NOTES = 3


def _loads_args(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe(text: str) -> str:
    enc = sys.stdout.encoding or "utf-8"
    return text.encode(enc, errors="replace").decode(enc)


class Agent:
    def __init__(
        self,
        task: str,
        workdir: str,
        interactive: bool = False,
        use_browser: bool = True,
        headless: bool = True,
        model: str | None = None,
        max_steps: int | None = None,
        review_gates: bool = False,
        stream: bool = False,
        sandbox: bool = False,
    ):
        self.task = task
        self.workdir = os.path.abspath(workdir)
        os.makedirs(self.workdir, exist_ok=True)
        self.interactive = interactive
        self.use_browser = use_browser
        self.max_steps = max_steps or 40
        self.review_gates = review_gates
        self.stream = stream
        self.sandbox = sandbox
        self.executor = ToolExecutor(
            self.workdir, use_browser, interactive, headless=headless, task=task, sandbox=sandbox
        )
        self.history = RunHistory(self.workdir, task)
        self.llm = LLMClient(model=model)
        self._retriever: RetrieverProtocol | None = None
        self._retriever_notes: tuple[str, ...] = ()

    def _system(self, phase: str) -> str:
        notes = self.executor.notes
        if notes:
            if len(notes) <= RETRIEVAL_K + RECENT_NOTES:
                selected = notes
            else:
                if tuple(notes) != self._retriever_notes:
                    self._retriever_notes = tuple(notes)
                    self._retriever = build_retriever(notes)
                assert self._retriever is not None
                top = self._retriever.search(f"{self.task} {phase}", k=RETRIEVAL_K)
                selected = list(dict.fromkeys(top + notes[-RECENT_NOTES:]))
            rendered = "\n".join(f"- {n}" for n in selected)
        else:
            rendered = "(empty - run research first)"
        return SYSTEM_BASE.format(workdir=self.workdir, task=self.task, notes=rendered)

    def _run_phase(self, name: str) -> str | None:
        print(f"\n=== PHASE: {name.upper()} ===")
        messages: list[dict] = [
            {"role": "system", "content": self._system(name)},
            {"role": "user", "content": PHASES[name]},
        ]
        done_summary: str | None = None

        for step in range(self.max_steps):
            messages[0] = {"role": "system", "content": self._system(name)}
            message = self._chat(messages)
            if message.tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in message.tool_calls
                    ],
                }
                messages.append(assistant_msg)
                handled = self._execute_tool_calls(message.tool_calls)
                for tc, fname, summary, result in handled:
                    if summary is not None:
                        done_summary = summary
                    self.history.record(
                        "tool",
                        step=step,
                        tool=fname,
                        arguments=(tc.function.arguments or "")[:200],
                        result=str(result)[:300],
                    )
                    print(_safe(f"[{step}] {fname}: {result[:400]}"))
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                if done_summary is not None:
                    self.history.record("phase", phase=name, summary=done_summary)
                    return done_summary
            else:
                messages.append({"role": "assistant", "content": message.content or ""})
                messages.append({"role": "user", "content": "Continue. Call the appropriate tool to make progress. When the phase is complete, call finish."})

            messages = self._compact(messages, name)

        print(_safe(f"[WARN] {name.upper()} phase exceeded {self.max_steps} steps; forcing phase end."))
        self.history.record("phase", phase=name, summary=done_summary or "ended after step limit")
        return done_summary or f"Phase {name} ended after hitting the step limit."

    def _handle_tool_call(self, tc) -> tuple:
        fname = tc.function.name
        fargs = _loads_args(tc.function.arguments)
        result = self.executor.execute(fname, fargs)
        summary = fargs.get("summary") if fname == "finish" else None
        return tc, fname, summary, result

    def _execute_tool_calls(self, tool_calls) -> list[tuple]:
        if len(tool_calls) <= 1:
            return [self._handle_tool_call(tool_calls[0])]
        with ThreadPoolExecutor(max_workers=min(len(tool_calls), MAX_PARALLEL)) as pool:
            return list(pool.map(self._handle_tool_call, tool_calls))

    def _compact(self, messages: list[dict], phase: str) -> list[dict]:
        if len(messages) <= MAX_MESSAGES:
            return messages
        last_assistant = -1
        for i, message in enumerate(messages):
            if message["role"] == "assistant":
                last_assistant = i
        if last_assistant <= 1:
            return messages[:MAX_MESSAGES]
        keep = messages[last_assistant:]
        old = messages[1:last_assistant]
        summary = self._summarize(old, phase)
        if summary:
            return [messages[0], {"role": "user", "content": f"[Compressed summary of earlier context]\n{summary}"}] + keep
        return [messages[0]] + keep

    def _summarize(self, old: list[dict], phase: str) -> str:
        try:
            prompt = (
                "Summarize the following agent conversation history concisely, keeping important "
                f"decisions, facts, and tool outputs from the {phase} phase. Return only the summary.\n\n"
                + json.dumps(old, ensure_ascii=True)[:20000]
            )
            message = self.llm.chat([{"role": "user", "content": prompt}], temperature=0.0)
            return (message.content or "").strip()
        except Exception:
            return ""

    def _review_gate(self, phase: str, summary: str) -> str:
        print(_safe(f"\n[GATE] {phase.upper()} phase complete."))
        print(_safe(f"Summary: {summary[:500]}"))
        answer = input("[YOU] (Enter=continue, s=skip remaining phases, a=abort) ").strip().lower()
        if answer in ("s", "skip"):
            return "skip"
        if answer in ("a", "abort"):
            return "abort"
        return "continue"

    def _chat(self, messages: list[dict]):
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                if self.stream:
                    print("  ", end="", flush=True)
                    message = self.llm.chat_stream(
                        messages,
                        tools=TOOL_SCHEMAS,
                        on_delta=lambda delta: print(_safe(delta), end="", flush=True),
                    )
                    print(flush=True)
                    return message
                return self.llm.chat(messages, tools=TOOL_SCHEMAS)
            except Exception as exc:
                last_error = exc
                wait = 3 * (attempt + 1)
                print(_safe(f"[LLM] call failed ({type(exc).__name__}: {exc}). Retrying in {wait}s..."))
                time.sleep(wait)
        raise RuntimeError(f"LLM unavailable after {MAX_RETRIES} attempts: {last_error}")

    def run(self) -> str:
        report: list[str] = []
        try:
            for phase in ("research", "build", "verify", "upgrade"):
                summary = self._run_phase(phase)
                report.append(f"## {phase.upper()}\n{summary}\n")
                if self.review_gates and phase != "upgrade":
                    decision = self._review_gate(phase, summary or "")
                    if decision == "abort":
                        report.append(f"(aborted by user after {phase.upper()} phase)")
                        break
                    if decision == "skip":
                        report.append("(remaining phases skipped by user)")
                        break
        finally:
            self.executor.close()
        final = "\n".join(report)
        self.history.record("report", report=final)
        return final
