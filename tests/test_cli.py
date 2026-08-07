import sys

from agent.cli import build_parser


def test_parser_flags():
    parser = build_parser()
    ns = parser.parse_args(["--review-gates", "--log", "x.log", "do", "something"])
    assert ns.review_gates is True
    assert ns.log == "x.log"
    assert ns.prompt == ["do", "something"]


def test_main_writes_log_and_report(monkeypatch, tmp_path, capsys):
    import agent.cli as cli

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def run(self):
            return "RESEARCH complete\nBUILD complete"

    monkeypatch.setattr(cli, "Agent", FakeAgent)
    monkeypatch.setattr(sys, "argv", ["autonomous-agent", "--workdir", str(tmp_path), "--no-browser", "build", "hello"])

    code = cli.main()
    assert code == 0
    log_file = tmp_path / "agent_run.log"
    assert log_file.exists()
    text = log_file.read_text(encoding="utf-8")
    assert "FINAL REPORT" in text
    assert "RESEARCH complete" in text


def test_main_respects_no_log(monkeypatch, tmp_path, capsys):
    import agent.cli as cli

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

        def run(self):
            return "done"

    monkeypatch.setattr(cli, "Agent", FakeAgent)
    monkeypatch.setattr(sys, "argv", ["autonomous-agent", "--workdir", str(tmp_path), "--no-browser", "--no-log", "build", "hello"])
    code = cli.main()
    assert code == 0
    assert not (tmp_path / "agent_run.log").exists()
