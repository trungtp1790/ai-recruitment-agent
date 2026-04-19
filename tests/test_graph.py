from app.graph.graph import build_recruitment_graph


def test_graph_job_search_flow():
    graph = build_recruitment_graph()
    result = graph.invoke({"session_id": "s1", "user_query": "Tim viec AI Engineer luong 20-30", "entities": {}})

    assert result["intent"] == "job_search"
    assert result["salary"]["min_value"] == 20_000_000
    assert result["salary"]["max_value"] == 30_000_000
    assert "response" in result


def test_graph_has_out_of_scope_fallback():
    graph = build_recruitment_graph()
    result = graph.invoke({"session_id": "s2", "user_query": "thoi tiet hom nay the nao", "entities": {}})
    assert result["intent"] in {"out_of_scope", "chitchat"}
    assert "response" in result
