import agent.agent as agent_module
from agent import Agent
from tests.fakes import FakeLLM, FakeMessage, tc


def test_agent_runs_all_phases(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "LLMClient", FakeLLM)
    agent = Agent(task="build a hello app", workdir=str(tmp_path), use_browser=False, max_steps=12)
    report = agent.run()
    assert "RESEARCH complete" in report
    assert "BUILD complete" in report
    assert "VERIFY complete" in report
    assert "UPGRADE complete" in report
    assert "step limit" not in report


def test_agent_writes_project_and_notes(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "LLMClient", FakeLLM)
    agent = Agent(task="build a hello app", workdir=str(tmp_path), use_browser=False, max_steps=12)
    agent.run()
    assert (tmp_path / "app.py").exists()
    assert (tmp_path / "research_notes.md").exists()


class ParallelLLM(FakeLLM):
    def chat(self, messages, tools=None, temperature=0.2):
        last_user = next(m for m in reversed(messages) if m["role"] == "user")
        plans = {
            "RESEARCH": [["append_note", "append_note"], ["finish"]],
            "VERIFY": [["write_file", "write_file"], ["finish"]],
        }
        for phase_name, plan in plans.items():
            if f"PHASE: {phase_name}" in last_user["content"]:
                idx = self.counts.get(phase_name, 0)
                self.counts[phase_name] = idx + 1
                step = plan[min(idx, len(plan) - 1)]
                calls = []
                for tool in step:
                    if tool == "finish":
                        calls.append(tc("finish", {"summary": f"{phase_name} complete"}))
                    elif tool == "append_note":
                        calls.append(tc("append_note", {"note": f"note {idx}-{len(calls)}"}))
                    elif tool == "write_file":
                        calls.append(tc("write_file", {"path": f"file_{idx}_{len(calls)}.txt", "content": "X"}))
                return FakeMessage(None, calls)
        return super().chat(messages, tools=tools, temperature=temperature)


def test_parallel_tool_calls_execute_all(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "LLMClient", ParallelLLM)
    agent = Agent(task="hello", workdir=str(tmp_path), use_browser=False, max_steps=12)
    report = agent.run()
    assert "VERIFY complete" in report
    assert (tmp_path / "file_0_0.txt").exists()
    assert (tmp_path / "file_0_1.txt").exists()
    notes = (tmp_path / "research_notes.md").read_text(encoding="utf-8")
    assert "note 0-0" in notes
    assert "note 0-1" in notes
