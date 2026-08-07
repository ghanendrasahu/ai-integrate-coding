from agent.retrieval import Retriever


def test_empty_notes():
    assert Retriever([]).search("anything", k=5) == []


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
