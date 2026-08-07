import pytest
from types import SimpleNamespace

from agent.config import load_agent_toml, resolve_config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("AGENT_MODEL", "AGENT_PROVIDER", "AGENT_API_BASE", "AGENT_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_load_agent_toml_missing(tmp_path):
    assert load_agent_toml(str(tmp_path / "nope.toml")) == {}


def test_resolve_defaults():
    cfg = resolve_config(SimpleNamespace())
    assert cfg["max_steps"] == 40
    assert cfg["use_browser"] is True
    assert cfg["review_gates"] is False


def test_toml_values(tmp_path):
    (tmp_path / "agent.toml").write_text(
        "[agent]\nmax_steps = 12\ninteractive = true\n\n[llm]\nmodel = \"gemini-2.0-flash\"\n",
        encoding="utf-8",
    )
    cfg = resolve_config(SimpleNamespace(), toml_path=str(tmp_path / "agent.toml"))
    assert cfg["max_steps"] == 12
    assert cfg["interactive"] is True
    assert cfg["model"] == "gemini-2.0-flash"


def test_cli_overrides_toml(tmp_path):
    (tmp_path / "agent.toml").write_text(
        "[agent]\nmax_steps = 12\n\n[llm]\nmodel = \"gemini\"\n",
        encoding="utf-8",
    )
    args = SimpleNamespace(
        max_steps=30, model="gpt-4o-mini", interactive=False,
        no_browser=True, show_browser=False, review_gates=False, log=None,
    )
    cfg = resolve_config(args, toml_path=str(tmp_path / "agent.toml"))
    assert cfg["max_steps"] == 30
    assert cfg["model"] == "gpt-4o-mini"
    assert cfg["use_browser"] is False


def test_env_overrides_toml(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_MODEL", "env-model")
    (tmp_path / "agent.toml").write_text(
        "[llm]\nmodel = \"toml-model\"\n",
        encoding="utf-8",
    )
    cfg = resolve_config(SimpleNamespace(), toml_path=str(tmp_path / "agent.toml"))
    assert cfg["model"] == "env-model"


def test_stream_and_sandbox_flags(tmp_path):
    args = SimpleNamespace(stream=True, sandbox=True)
    cfg = resolve_config(args, toml_path=str(tmp_path / "agent.toml"))
    assert cfg["stream"] is True
    assert cfg["sandbox"] is True


def test_stream_and_sandbox_toml(tmp_path):
    (tmp_path / "agent.toml").write_text(
        "[agent]\nstream = true\nsandbox = true\n",
        encoding="utf-8",
    )
    cfg = resolve_config(SimpleNamespace(), toml_path=str(tmp_path / "agent.toml"))
    assert cfg["stream"] is True
    assert cfg["sandbox"] is True
