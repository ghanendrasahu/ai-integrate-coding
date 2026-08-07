import os

from openai import OpenAI

DEFAULT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("AGENT_MODEL", "qwen2.5-coder:14b")


def _ollama_available() -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(OLLAMA_BASE + "/models", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


class LLMClient:
    def __init__(self, model: str | None = None):
        provider = os.getenv("AGENT_PROVIDER", "").lower().strip()
        api_key = os.getenv("AGENT_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("AGENT_API_BASE") or os.getenv("OPENAI_BASE_URL")

        if provider == "ollama" or (not api_key and not base_url and _ollama_available()):
            self.model = model or OLLAMA_MODEL
            self.client = OpenAI(base_url=OLLAMA_BASE, api_key="ollama")
            self.provider = "ollama"
        elif api_key or base_url:
            self.model = model or DEFAULT_MODEL
            self.client = OpenAI(api_key=api_key or "none", base_url=base_url or None)
            self.provider = "openai-compatible"
        else:
            raise RuntimeError(
                "No LLM backend configured. Set AGENT_API_KEY (OpenAI/Gemini) + "
                "optional AGENT_API_BASE, or set AGENT_PROVIDER=ollama with Ollama running."
            )

    def chat(self, messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.2):
        kwargs: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs).choices[0].message
