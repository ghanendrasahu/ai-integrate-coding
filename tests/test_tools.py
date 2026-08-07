import pytest

from agent.tools import ToolExecutor


@pytest.fixture
def executor(tmp_path):
    return ToolExecutor(str(tmp_path), False, False)


def test_write_read_list(executor, tmp_path):
    result = executor.execute("write_file", {"path": "test.txt", "content": "hi"})
    assert "Wrote" in result
    assert executor.execute("read_file", {"path": "test.txt"}) == "hi"
    listing = executor.execute("list_dir", {"path": "."})
    assert "test.txt" in listing


def test_run_command_success(executor):
    out = executor.execute("run_command", {"command": 'python -c "print(42)"'})
    assert "EXIT CODE: 0" in out
    assert "42" in out


def test_run_command_failure(executor):
    out = executor.execute("run_command", {"command": 'python -c "raise SystemExit(3)"'})
    assert "EXIT CODE: 3" in out


def test_run_command_timeout(executor):
    out = executor.execute("run_command", {"command": 'python -c "import time; time.sleep(5)"', "timeout": 1})
    assert "timed out" in out


def test_append_note_disabled_browser(tmp_path):
    ex = ToolExecutor(str(tmp_path), False, False)
    assert ex.execute("web_search", {"query": "x"}) != "ERROR: unknown tool 'web_search'"
    assert "disabled" in ex.execute("web_search", {"query": "x"}).lower()


def test_ask_user_disabled(executor):
    assert "disabled" in executor.execute("ask_user", {"question": "anything?"})


def test_finish_tool(executor):
    assert executor.execute("finish", {"summary": "done"}) == "Phase complete."


def test_unknown_tool(executor):
    assert "unknown tool" in executor.execute("no_such_tool", {})


def test_notes_persist_to_disk(tmp_path):
    ToolExecutor(str(tmp_path), False, False).execute("append_note", {"note": "fact A"})
    reloaded = ToolExecutor(str(tmp_path), False, False)
    assert reloaded.notes == ["fact A"]
    assert (tmp_path / "research_notes.md").exists()


def test_notes_loaded_across_runs_skip_bad_lines(tmp_path):
    notes_file = tmp_path / "research_notes.md"
    notes_file.write_text("- good note\nmalformed line\n- second note\n", encoding="utf-8")
    reloaded = ToolExecutor(str(tmp_path), False, False)
    assert reloaded.notes == ["good note", "second note"]


def test_close_without_browsers(executor):
    executor.close()
    executor.execute("append_note", {"note": "after close"})
    assert executor.notes == ["after close"]
