import os
import subprocess
import threading

from .browser import Browser

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using Chrome to retrieve answers, docs, best practices and current versions relevant to the task. Returns a list of results with title, url and snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query, as specific as possible."},
                    "num_results": {"type": "integer", "description": "How many results to return (1-10).", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_open",
            "description": "Open a specific URL in Chrome and return its readable text content. Use to read the full content of a promising search result.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "The absolute URL to open."}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_note",
            "description": "Save an important research finding into the project knowledge base (RAG notes). The note stays available to every later step. One fact per note, cite the source.",
            "parameters": {
                "type": "object",
                "properties": {"note": {"type": "string", "description": "The fact or finding to remember."}},
                "required": ["note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the files and directories inside a given path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory path. Defaults to the working directory."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Path to the file to read."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content. Parent directories are created automatically. Use UTF-8.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file to write."},
                    "content": {"type": "string", "description": "Full content of the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the working directory and return its exit code, stdout and stderr. Use to install dependencies, run tests, build, lint or start the application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to run."},
                    "timeout": {"type": "integer", "description": "Timeout in seconds.", "minimum": 5, "maximum": 600},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the human a question. Use ONLY when truly blocked: a required secret, or a genuinely ambiguous requirement that no reasonable default can resolve.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string", "description": "The question for the human."}},
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Signal that the current phase is complete. Provide a concise summary of what was done.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string", "description": "Summary of what was accomplished in this phase."}},
                "required": ["summary"],
            },
        },
    },
]

MAX_OUTPUT_CHARS = 30000


class ToolExecutor:
    def __init__(self, workdir: str, use_browser: bool, interactive: bool, headless: bool = True):
        self.workdir = workdir
        self.use_browser = use_browser
        self.headless = headless
        self.interactive = interactive
        self.notes_path = os.path.join(workdir, "research_notes.md")
        self.notes: list[str] = self._load_notes()
        self._notes_lock = threading.Lock()
        self._browser_thread = threading.local()
        self._browsers: list[Browser] = []
        self._browsers_lock = threading.Lock()

    def _load_notes(self) -> list[str]:
        try:
            with open(self.notes_path, "r", encoding="utf-8") as fh:
                return [line.strip()[2:] for line in fh if line.startswith("- ")]
        except OSError:
            return []

    def _save_notes(self) -> None:
        try:
            with open(self.notes_path, "w", encoding="utf-8") as fh:
                for note in self.notes:
                    fh.write(f"- {note}\n")
        except OSError:
            pass

    def _browser_for_thread(self) -> Browser | None:
        if not self.use_browser:
            return None
        browser = getattr(self._browser_thread, "browser", None)
        if browser is None:
            browser = Browser(headless=self.headless)
            with self._browsers_lock:
                self._browsers.append(browser)
            self._browser_thread.browser = browser
        return browser

    def close(self) -> None:
        with self._browsers_lock:
            browsers, self._browsers = self._browsers, []
        for browser in browsers:
            try:
                browser.close()
            except Exception:
                pass

    def execute(self, name: str, args: dict) -> str:
        handler = getattr(self, f"_exec_{name}", None)
        if handler is None:
            return f"ERROR: unknown tool '{name}'"
        try:
            return str(handler(args))
        except Exception as exc:
            return f"ERROR executing {name}: {type(exc).__name__}: {exc}"

    def _trim(self, text: str) -> str:
        text = str(text)
        if len(text) > MAX_OUTPUT_CHARS:
            text = text[:MAX_OUTPUT_CHARS] + " ... [truncated]"
        return text

    def _to_str(self, data: object) -> str:
        if data is None:
            return ""
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)

    def _abs(self, path: str) -> str:
        if not os.path.isabs(path):
            path = os.path.join(self.workdir, path)
        return os.path.normpath(path)

    def _exec_web_search(self, args: dict) -> str:
        browser = self._browser_for_thread()
        if browser is None:
            return "ERROR: browser is disabled (use --no-browser implies no web research)."
        results = browser.search(args["query"], int(args.get("num_results", 6)))
        if not results:
            return "No results found."
        lines = [f"{i + 1}. {r['title']}\n   URL: {r['url']}\n   {r['snippet']}" for i, r in enumerate(results)]
        return self._trim("\n\n".join(lines))

    def _exec_web_open(self, args: dict) -> str:
        browser = self._browser_for_thread()
        if browser is None:
            return "ERROR: browser is disabled (use --no-browser implies no web research)."
        return self._trim(browser.fetch_text(args["url"]))

    def _exec_append_note(self, args: dict) -> str:
        with self._notes_lock:
            self.notes.append(str(args["note"]))
            self._save_notes()
            return f"Note saved. Total notes: {len(self.notes)}"

    def _exec_list_dir(self, args: dict) -> str:
        path = self._abs(args.get("path", "."))
        entries = []
        for entry in sorted(os.scandir(path), key=lambda e: e.name):
            kind = "DIR " if entry.is_dir() else "FILE"
            entries.append(f"{kind} {entry.name}")
        return "\n".join(entries) if entries else "(empty directory)"

    def _exec_read_file(self, args: dict) -> str:
        path = self._abs(args["path"])
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return self._trim(fh.read())

    def _exec_write_file(self, args: dict) -> str:
        path = self._abs(args["path"])
        os.makedirs(os.path.dirname(path) or self.workdir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(args["content"])
        return f"Wrote {path} ({len(args['content'])} chars)"

    def _exec_run_command(self, args: dict) -> str:
        timeout = int(args.get("timeout", 120))
        try:
            proc = subprocess.run(
                args["command"], shell=True, capture_output=True, text=True,
                cwd=self.workdir, timeout=timeout, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            return (
                f"ERROR: command timed out after {timeout}s\n"
                f"{self._trim(self._to_str(exc.stdout))}\n"
                f"{self._trim(self._to_str(exc.stderr))}"
            )
        out = self._trim(self._to_str(proc.stdout) + self._to_str(proc.stderr))
        return f"EXIT CODE: {proc.returncode}\nOUTPUT:\n{out if out else '(no output)'}"

    def _exec_ask_user(self, args: dict) -> str:
        if not self.interactive:
            return (
                "Ask the user is disabled (autonomous mode). Do not use it. "
                "Make a reasonable, well-documented decision yourself and continue."
            )
        print(f"\n[AGENT] QUESTION: {args['question']}")
        answer = input("[YOU] ")
        return f"User answered: {answer}"

    def _exec_finish(self, args: dict) -> str:
        return "Phase complete."
