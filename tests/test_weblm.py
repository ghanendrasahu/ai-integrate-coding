from agent.weblm import WebAI, best_answer, _score, _trim_answer


def test_best_answer_picks_code_rich_reply():
    answers = [
        ("chatgpt", "short vague reply no code"),
        ("gemini", "Use Flask:\n```python\ndef app():\n    return Flask(__name__)\n```\nSchema: ..."),
    ]
    chosen = best_answer(answers)
    assert "```" in chosen


def test_best_answer_empty():
    assert best_answer([]) == ""


def test_best_answer_skips_no_answer_errors():
    answers = [
        ("chatgpt", "[no answer received]"),
        ("gemini", "a real helpful reply with details"),
    ]
    chosen = best_answer(answers)
    assert "real helpful reply" in chosen


def test_score_rewards_code_and_length():
    vocab = {"flask", "api", "app"}
    with_code = "start ```python\nx=1\n```\nend " * 5
    without = "skip " * 3
    assert _score(with_code, vocab) > _score(without, vocab)


def test_trim_answer_caps_length():
    long = "word " * 99999
    trimmed = _trim_answer(long)
    assert "[truncated]" in trimmed
    assert len(trimmed) <= 13000


def test_providers_filtered():
    web_ai = WebAI("", providers=["chatgpt", "does_not_exist"])
    assert web_ai.providers == ["chatgpt"]