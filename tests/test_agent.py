import agent.agent as agent_module
from agent import Agent
from tests.fakes import FakeLLM


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
