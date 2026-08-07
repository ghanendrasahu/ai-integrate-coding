import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


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
