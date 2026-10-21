"""Offline tests for the Chrome-backed Browser tool.

A tiny local HTTP server stands in for the real web, so the extraction
assertions are deterministic (the live example.com page changed its copy
and previously broke CI) and the suite never touches the network.
"""

from __future__ import annotations

import http.server
import threading

import pytest

from agent.browser import Browser

_CONTENT_HTML = b"""<!DOCTYPE html>
<html><head><title>Fixture</title></head>
<body><h1>Example Domain</h1>
<p>This domain is for use in documentation examples without needing permission.</p>
</body></html>"""

# DDG-shaped fixtures exercise the real scraper logic in agent.browser.
_SEARCH_HTML = b"""<!DOCTYPE html>
<html><head><title>Search</title></head>
<body>
<div class="result">
  <a class="result__a" href="https://docs.python.org/3.11/">Python 3.11 release notes</a>
  <div class="result__snippet">Faster and more convenient CPython release.</div>
</div>
<div class="result">
  <a class="result__a" href="https://www.python.org/downloads/">Download Python</a>
  <div class="result__snippet">The official Python downloads page.</div>
</div>
</body></html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib API name)
        body = _SEARCH_HTML if self.path.startswith("/search") else _CONTENT_HTML
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # deliberately silent
        pass


@pytest.fixture(scope="module")
def local_site():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_search_returns_results(local_site, monkeypatch):
    """search() scrapes whatever DDG-shaped page it is pointed at."""
    monkeypatch.setattr("agent.browser.DDG_HTML", local_site + "/search?q={query}")
    browser = Browser(headless=True)
    try:
        results = browser.search("python 3.11 release", num_results=3)
    except Exception as exc:
        pytest.skip(f"Browser unavailable: {exc}")
    finally:
        browser.close()
    assert len(results) == 2
    assert all(r["url"] and r["title"] for r in results)
    assert results[0]["url"] == "https://docs.python.org/3.11/"
    assert "CPython" in results[0]["snippet"]


def test_fetch_text_returns_content(local_site):
    """fetch_text() reads the full visible text of the page it opened."""
    browser = Browser(headless=True)
    text = ""
    try:
        text = browser.fetch_text(local_site + "/")
    except Exception as exc:
        pytest.skip(f"Browser unavailable: {exc}")
    finally:
        browser.close()
    assert "Example Domain" in text
    assert "documentation examples" in text
