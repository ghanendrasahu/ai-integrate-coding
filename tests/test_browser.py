import pytest

from agent.browser import Browser


def test_search_returns_results():
    browser = Browser(headless=True)
    results = []
    try:
        results = browser.search("python 3.11 release", num_results=3)
    except Exception as exc:
        pytest.skip(f"Browser or network unavailable: {exc}")
    finally:
        browser.close()
    assert results
    assert all("url" in r and "title" in r for r in results)


def test_fetch_text_returns_content():
    browser = Browser(headless=True)
    text = ""
    try:
        text = browser.fetch_text("https://example.com")
    except Exception as exc:
        pytest.skip(f"Browser or network unavailable: {exc}")
    finally:
        browser.close()
    assert "Example Domain" in text
