import collections
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext as PWContext
    from playwright.sync_api import Playwright as PWPlaywright

PROVIDERS = {
    "chatgpt": {"url": "https://chatgpt.com/"},
    "gemini": {"url": "https://gemini.google.com/app"},
}

DEFAULT_PROVIDERS: list[str] = os.getenv("WEB_AI_PROVIDERS", "chatgpt,gemini").replace(" ", "").split(",")

MAX_ANSWER_CHARS = 12000
QUERY_TIMEOUT_SECONDS = 240

FIND_INPUT_JS = """
() => {
  const candidates = document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"]');
  for (const el of candidates) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && el.offsetParent !== null) return true;
  }
  return false;
}
"""

FILL_INPUT_JS = """
prompt => {
  const candidates = document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"]');
  for (const el of candidates) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && el.offsetParent === null) continue;
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
      el.value = prompt;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      el.textContent = prompt;
      el.dispatchEvent(new InputEvent('input', { bubbles: true, data: prompt }));
    }
    el.focus();
    return true;
  }
  return false;
}
"""

EXTRACT_JS = """
() => {
  const selectors = [
    '[data-message-author-role="assistant"]',
    '.markdown',
    '.model-response',
    '.response',
    '[data-testid="conversation-turn"]',
    'message-content'
  ];
  for (const sel of selectors) {
    const nodes = document.querySelectorAll(sel);
    if (nodes.length) {
      const last = nodes[nodes.length - 1];
      const text = last && last.innerText ? last.innerText.trim() : '';
      if (text) return text;
    }
  }
  return '';
}
"""


def _trim_answer(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text or "").strip()
    if len(collapsed) > MAX_ANSWER_CHARS:
        collapsed = collapsed[:MAX_ANSWER_CHARS] + " ... [truncated]"
    return collapsed


def _score(answer: str, vocabulary: set[str]) -> float:
    if not answer:
        return -1000.0
    code_blocks = len(re.findall(r"```", answer))
    length = min(len(answer), 4000)
    matched = sum(1 for word in vocabulary if word in answer)
    return 30.0 * min(code_blocks, 5) + 0.005 * length + matched


def _top_words(answers: list[tuple[str, str]]) -> set[str]:
    counter: collections.Counter = collections.Counter()
    for _, text in answers:
        for word in re.findall(r"[a-z0-9_]{3,}", text.lower()):
            counter[word] += 1
    return {word for word, _ in counter.most_common(50)}


def best_answer(answers: list[tuple[str, str]]) -> str:
    if not answers:
        return ""
    vocabulary = _top_words(answers)
    return max(answers, key=lambda item: _score(item[1], vocabulary))[1]


def format_answers(answers: list[tuple[str, str]]) -> str:
    if not answers:
        return "No answers received from any provider."
    chosen = best_answer(answers)
    parts = ["BEST ANSWER:", chosen, "", "ALL ANSWERS BY PROVIDER:"]
    for name, text in answers:
        is_best = text == chosen
        marker = " [CHOSEN]" if is_best else ""
        parts.append(f"--- {name}{marker} ---")
        parts.append(_trim_answer(text)[:1600])
    return "\n".join(parts)


class WebAI:
    def __init__(
        self,
        workdir: str,
        headless: bool = True,
        providers: list[str] | None = None,
    ):
        self.workdir = os.path.abspath(workdir)
        self.headless = headless
        self.providers = [p for p in (providers or DEFAULT_PROVIDERS) if p in PROVIDERS]
        self._pw: PWPlaywright | None = None
        self._context: PWContext | None = None
        self._profile_dir = os.path.join(self.workdir, "web_ai_profile")

    def _start(self) -> None:
        if self._context is not None:
            return
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        browser = self._pw.chromium
        try:
            self._context = browser.launch_persistent_context(
                user_data_dir=self._profile_dir, channel="chrome", headless=self.headless
            )
        except Exception:
            self._context = browser.launch_persistent_context(
                user_data_dir=self._profile_dir, headless=self.headless
            )

    def _ask_one(self, name: str, prompt: str) -> str:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        self._start()
        if self._context is None:
            return "[error: failed to start browser]"
        page = self._context.new_page()
        try:
            page.goto(PROVIDERS[name]["url"], timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            try:
                page.wait_for_function(FIND_INPUT_JS, timeout=20000)
            except PlaywrightTimeout:
                return "[no answer] input not found (not logged in or layout changed)"
            page.evaluate(FILL_INPUT_JS, prompt)
            page.keyboard.press("Enter")
            wait_until_stable(page)
            return _trim_answer(str(page.evaluate(EXTRACT_JS) or "")) or "[no answer received]"
        except Exception as exc:
            return f"[error: {type(exc).__name__}: {exc}]"
        finally:
            page.close()

    def ask_all(self, prompt: str) -> list[tuple[str, str]]:
        if not self.providers:
            return []
        with ThreadPoolExecutor(max_workers=len(self.providers)) as pool:
            return list(pool.map(lambda name: (name, self._ask_one(name, prompt)), self.providers))

    def best(self, prompt: str) -> tuple[str, list[tuple[str, str]]]:
        answers = self.ask_all(prompt)
        return best_answer(answers), answers

    def close(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
        self._context = None
        self._pw = None


def wait_until_stable(page, timeout: int = QUERY_TIMEOUT_SECONDS) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        page.wait_for_timeout(2000)
        try:
            snippet = _trim_answer(str(page.evaluate(EXTRACT_JS) or ""))
        except Exception:
            snippet = ""
        if snippet and snippet == last:
            break
        last = snippet