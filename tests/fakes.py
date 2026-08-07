import json
from types import SimpleNamespace


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


def tc(name, args):
    return SimpleNamespace(
        id="call_1",
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


PHASE_PLANS = {
    "RESEARCH": ["web_search", "append_note", "finish"],
    "BUILD": ["write_file", "finish"],
    "VERIFY": ["run_command", "finish"],
    "UPGRADE": ["run_command", "finish"],
}

TOOL_ARGS = {
    "web_search": {"query": "q", "num_results": 2},
    "append_note": {"note": "research fact"},
    "write_file": {
        "path": "app.py",
        "content": "def main():\n    print('hello')\n\nif __name__ == '__main__':\n    main()\n",
    },
    "run_command": {"command": "python app.py"},
    "finish": {"summary": "PHASE complete"},
}


class FakeLLM:
    def __init__(self, model=None):
        self.counts = {}

    def chat(self, messages, tools=None, temperature=0.2):
        last_user = next(m for m in reversed(messages) if m["role"] == "user")
        phase = next((p for p in PHASE_PLANS if f"PHASE: {p}" in last_user["content"]), None)
        assert phase is not None
        plan = PHASE_PLANS[phase]
        idx = self.counts.get(phase, 0)
        self.counts[phase] = idx + 1
        step = plan[min(idx, len(plan) - 1)]
        args = dict(TOOL_ARGS[step])
        if step == "finish":
            args = {"summary": f"{phase} complete"}
        return FakeMessage(None, [tc(step, args)])
