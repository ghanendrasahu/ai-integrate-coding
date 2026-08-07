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
    notes = list((tmp_path / "research_notes").glob("*.md"))
    assert len(notes) == 1
    assert notes[0].name == "build-a-hello-app.md"


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
    notes = (tmp_path / "research_notes" / "hello.md").read_text(encoding="utf-8")
    assert "note 0-0" in notes
    assert "note 0-1" in notes


class BurstLLM(FakeLLM):
    def chat(self, messages, tools=None, temperature=0.2):
        last_user = next(m for m in reversed(messages) if m["role"] == "user")
        if last_user["content"].startswith("PHASE: RESEARCH"):
            self.pending_phase = "RESEARCH"
            idx = self.counts.get("RESEARCH", 0)
            self.counts["RESEARCH"] = idx + 1
            if idx == 0:
                return FakeMessage(None, [tc("append_note", {"note": f"n{i}"}) for i in range(8)])
            return FakeMessage(None, [tc("finish", {"summary": "RESEARCH complete"})])
        return super().chat(messages, tools=tools, temperature=temperature)


def test_conversation_compaction_summarizes(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "LLMClient", BurstLLM)
    monkeypatch.setattr(agent_module, "MAX_MESSAGES", 5)
    agent = Agent(task="hello", workdir=str(tmp_path), use_browser=False, max_steps=12)
    report = agent.run()
    assert "RESEARCH complete" in report
    assert getattr(agent.llm, "summary_calls", 0) >= 1


def test_compact_directly(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "LLMClient", FakeLLM)
    monkeypatch.setattr(agent_module, "MAX_MESSAGES", 5)
    agent = Agent(task="hello", workdir=str(tmp_path), use_browser=False, max_steps=12)
    calls = []

    def fake_summarize(old, phase):
        calls.append((old, phase))
        return "compressed!"

    agent._summarize = fake_summarize
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "a", "tool_calls": []},
        {"role": "tool", "tool_call_id": "1", "content": "r1"},
        {"role": "tool", "tool_call_id": "2", "content": "r2"},
        {"role": "assistant", "content": "b", "tool_calls": []},
        {"role": "tool", "tool_call_id": "3", "content": "r3"},
    ]
    result = agent._compact(messages, "research")
    assert calls, "summarize should be invoked when over the message cap"
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user" and "Compressed summary" in result[1]["content"]
    assert result[-1]["role"] == "tool"


def test_review_gates_abort(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "LLMClient", FakeLLM)
    monkeypatch.setattr("builtins.input", lambda prompt="": "a")
    agent = Agent(task="hello", workdir=str(tmp_path), use_browser=False, max_steps=12, review_gates=True)
    report = agent.run()
    assert "aborted by user after RESEARCH phase" in report
    assert "BUILD complete" not in report


def test_streaming_mode_runs_all_phases(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(agent_module, "LLMClient", FakeLLM)
    agent = Agent(task="hello", workdir=str(tmp_path), use_browser=False, max_steps=12, stream=True)
    report = agent.run()
    assert "RESEARCH complete" in report
    assert "UPGRADE complete" in report


def test_sandbox_flag_passed_to_executor(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_module, "LLMClient", FakeLLM)
    agent = Agent(task="hello", workdir=str(tmp_path), use_browser=False, max_steps=12, sandbox=True)
    assert agent.executor.sandbox is True
    report = agent.run()
    assert "RESEARCH complete" in report
