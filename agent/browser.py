from typing import TYPE_CHECKING
from urllib.parse import quote

from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from playwright.sync_api import Browser as PBrowser
    from playwright.sync_api import Page, Playwright

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DDG_HTML = "https://html.duckduckgo.com/html/?q={query}"
MAX_TEXT_CHARS = 20000
SEARCH_JS = """
() => Array.from(document.querySelectorAll('.result')).map(r => {
  const a = r.querySelector('a.result__a');
  const s = r.querySelector('.result__snippet');
  return {
    title: a ? a.innerText.trim() : '',
    url: a ? a.href : '',
    snippet: s ? s.innerText.trim() : ''
  };
}).filter(x => x.url)
"""


class Browser:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw: Playwright | None = None
        self._browser: PBrowser | None = None
        self._page: Page | None = None

    def _page_instance(self) -> "Page":
        if self._page is None:
            self._pw = sync_playwright().start()
            try:
                self._browser = self._pw.chromium.launch(channel="chrome", headless=self.headless)
            except Exception:
                self._browser = self._pw.chromium.launch(headless=self.headless)
            context = self._browser.new_context(user_agent=DEFAULT_UA, viewport={"width": 1280, "height": 900})
            self._page = context.new_page()
        assert self._page is not None
        return self._page

    def search(self, query: str, num_results: int = 6) -> list[dict]:
        page = self._page_instance()
        page.goto(DDG_HTML.format(query=quote(query)), timeout=30000)
        page.wait_for_timeout(1200)
        results = page.evaluate(SEARCH_JS) or []
        return results[:max(1, min(num_results, 10))]

    def fetch_text(self, url: str) -> str:
        page = self._page_instance()
        page.goto(url, timeout=45000)
        page.wait_for_timeout(1500)
        text = page.evaluate("() => document.body ? document.body.innerText : ''")
        text = " ".join(text.split())
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + " ... [truncated]"
        return text

    def close(self):
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
        self._browser = None
        self._page = None
        self._pw = None
