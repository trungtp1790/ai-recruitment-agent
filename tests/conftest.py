import pytest


@pytest.fixture(autouse=True)
def fast_unit_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Speed up tests: skip Postgres TCP waits and Redis probes."""

    from app.graph.nodes import rag_retriever
    from app.memory import store as mem_store

    def _empty_jobs(
        positions: list[str],
        locations: list[str],
        skills: list[str],
        salary_min: int | None,
        salary_max: int | None,
        limit: int,
    ) -> list[dict]:
        return []

    monkeypatch.setattr(rag_retriever, "_query_jobs_from_db", _empty_jobs)
    monkeypatch.setattr(mem_store, "_redis", lambda: None)
