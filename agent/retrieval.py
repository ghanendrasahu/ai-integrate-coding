import json
import math
import os
import re
import urllib.request
from collections import Counter
from typing import Protocol

_TOKEN_RE = re.compile(r"[a-z0-9_]+")

_EMBED_CACHE: dict[str, list[float]] = {}


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class RetrieverProtocol(Protocol):
    def search(self, query: str, k: int = 8) -> list[str]: ...


class OpenAIEmbedder:
    def __init__(self, model: str | None = None):
        from openai import OpenAI

        self.client = OpenAI(
            api_key=os.getenv("AGENT_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("AGENT_API_BASE") or None,
        )
        self.model = model or os.getenv("AGENT_EMBED_MODEL", "text-embedding-3-small")
        self._cache: dict[str, list[float]] = _EMBED_CACHE

    def embed(self, texts: list[str]) -> list[list[float]]:
        missing = [text for text in texts if text not in self._cache]
        if missing:
            response = self.client.embeddings.create(model=self.model, input=missing)
            for text, item in zip(missing, response.data):
                self._cache[text] = item.embedding
        return [self._cache[text] for text in texts]


class OllamaEmbedder:
    def __init__(self, model: str | None = None, base: str = "http://localhost:11434"):
        self.model = model or os.getenv("AGENT_EMBED_MODEL", "nomic-embed-text")
        self.base = base.rstrip("/")
        self._cache: dict[str, list[float]] = _EMBED_CACHE

    def embed(self, texts: list[str]) -> list[list[float]]:
        for text in texts:
            if text not in self._cache:
                payload = json.dumps({"model": self.model, "input": text}).encode("utf-8")
                request = urllib.request.Request(
                    self.base + "/api/embeddings",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    self._cache[text] = json.loads(response.read())["embedding"]
        return [self._cache[text] for text in texts]


def make_embedder() -> Embedder | None:
    provider = os.getenv("AGENT_PROVIDER", "").lower()
    try:
        if provider == "ollama":
            return OllamaEmbedder()
        if os.getenv("AGENT_API_KEY") or os.getenv("OPENAI_API_KEY"):
            return OpenAIEmbedder()
    except Exception:
        return None
    return None


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


class Retriever:
    def __init__(self, notes: list[str]):
        self.notes = notes
        self.docs = [_tokens(note) for note in notes]
        df: dict[str, int] = {}
        for doc in self.docs:
            for token in set(doc):
                df[token] = df.get(token, 0) + 1
        self.idf = {token: math.log(1 + len(notes) / (1 + freq)) for token, freq in df.items()}

    def _vector(self, tokens: list[str]) -> dict[str, float]:
        counts = Counter(tokens)
        max_count = max(counts.values()) if counts else 1
        return {token: (count / max_count) * self.idf.get(token, 0.0) for token, count in counts.items()}

    def search(self, query: str, k: int = 8) -> list[str]:
        if not self.notes:
            return []
        query_vec = self._vector(_tokens(query))
        q_norm = math.sqrt(sum(v * v for v in query_vec.values())) or 1.0
        scored: list[tuple[float, int]] = []
        for idx, doc in enumerate(self.docs):
            doc_vec = self._vector(doc)
            d_norm = math.sqrt(sum(v * v for v in doc_vec.values())) or 1.0
            dot = sum(w * doc_vec.get(token, 0.0) for token, w in query_vec.items())
            scored.append((dot / (q_norm * d_norm), idx))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [self.notes[idx] for _, idx in scored[:k]]


class VectorRetriever:
    def __init__(self, notes: list[str], embedder: Embedder):
        self.notes = notes
        self.embedder = embedder
        self._vectors = embedder.embed(notes) if notes else []

    def search(self, query: str, k: int = 8) -> list[str]:
        if not self.notes:
            return []
        query_vec = self.embedder.embed([query])[0]
        scored = sorted(((_cosine(query_vec, vec), idx) for idx, vec in enumerate(self._vectors)), reverse=True)
        return [self.notes[idx] for _, idx in scored[:k]]


def build_retriever(notes: list[str]) -> RetrieverProtocol:
    embedder = make_embedder()
    if embedder is not None:
        try:
            return VectorRetriever(notes, embedder)
        except Exception:
            pass
    return Retriever(notes)
