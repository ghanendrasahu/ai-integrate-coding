import os
from types import SimpleNamespace

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

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

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
        on_delta=None,
    ):
        kwargs: dict = {"model": self.model, "messages": messages, "temperature": temperature, "stream": True}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        stream = self.client.chat.completions.create(**kwargs)
        content_parts: list[str] = []
        tool_call_chunks: dict[int, dict] = {}
        for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if getattr(delta, "content", None):
                content_parts.append(delta.content)
                if on_delta is not None:
                    on_delta(delta.content)
            if getattr(delta, "tool_calls", None):
                for tc in delta.tool_calls:
                    entry = tool_call_chunks.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    if getattr(tc, "id", None):
                        entry["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            entry["name"] += fn.name
                        if getattr(fn, "arguments", None):
                            entry["arguments"] += fn.arguments
        content = "".join(content_parts) or None
        if tool_call_chunks:
            tool_calls = [
                SimpleNamespace(
                    id=entry["id"] or f"call_{idx}",
                    type="function",
                    function=SimpleNamespace(name=entry["name"], arguments=entry["arguments"]),
                )
                for idx, entry in sorted(tool_call_chunks.items())
            ]
        else:
            tool_calls = []
        return SimpleNamespace(content=content, tool_calls=tool_calls)
