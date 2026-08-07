from agent.retrieval import Retriever, VectorRetriever, build_retriever


def test_empty_notes():
    assert Retriever([]).search("anything", k=5) == []


class FakeEmbedder:
    def embed(self, texts):
        vocab = ["python", "api", "jwt", "flask", "react"]
        return [[1.0 if word in text else 0.0 for word in vocab] for text in texts]


def test_vector_retriever_uses_embedder():
    notes = [
        "python fastapi rest api",
        "flask jwt authentication",
        "react hooks component",
    ]
    retriever = VectorRetriever(notes, FakeEmbedder())
    results = retriever.search("python api", k=1)
    assert results[0] == "python fastapi rest api"


def test_vector_retriever_empty_notes():
    assert VectorRetriever([], FakeEmbedder()).search("x", k=3) == []


def test_vector_retriever_k_larger_than_notes():
    retriever = VectorRetriever(["only note"], FakeEmbedder())
    results = retriever.search("python", k=10)
    assert results == ["only note"]


def test_build_retriever_falls_back_to_tfidf(monkeypatch):
    monkeypatch.setattr("agent.retrieval.make_embedder", lambda: None)
    retriever = build_retriever(["flask jwt auth", "pandas dataframe"])
    assert isinstance(retriever, Retriever)


def test_returns_top_k_most_relevant():
    notes = [
        "Flask 3.x uses the create_app application factory pattern",
        "JWT authentication with pyjwt requires a secret key",
        "React uses hooks like useState and useEffect",
    ]
    retriever = Retriever(notes)
    results = retriever.search("jwt token authentication best practices", k=2)
    assert results[0] == notes[1]
    assert "flask" in results[1].lower()


def test_k_larger_than_notes():
    retriever = Retriever(["only note about pandas"])
    results = retriever.search("pandas dataframe", k=10)
    assert results == ["only note about pandas"]


def test_unrelated_query_still_returns_ordered_notes():
    retriever = Retriever(["alpha beta gamma", "delta epsilon zeta"])
    results = retriever.search("delta", k=2)
    assert results[0] == "delta epsilon zeta"
