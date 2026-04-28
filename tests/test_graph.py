from app.graph.graph import build_recruitment_graph
from app.graph.nodes.responder import _build_job_list_response


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


def test_graph_job_search_with_vietnamese_accents():
    graph = build_recruitment_graph()
    result = graph.invoke({"session_id": "s3", "user_query": "AI Engineer lương 20-30 triệu", "entities": {}})
    assert result["intent"] == "job_search"
    assert "AI Engineer" in result["entities"]["position"]
    assert result["salary"]["min_value"] == 20_000_000
    assert result["salary"]["max_value"] == 30_000_000


def test_graph_job_search_with_english_salary_phrase():
    graph = build_recruitment_graph()
    result = graph.invoke(
        {
            "session_id": "s4",
            "user_query": "AI Engineer in Ho Chi Minh City with 20-30 million VND salary.",
            "entities": {},
        }
    )
    assert result["intent"] == "job_search"
    assert "AI Engineer" in result["entities"]["position"]
    assert "Ho Chi Minh City" in result["entities"]["location"]
    assert result["salary"]["min_value"] == 20_000_000
    assert result["salary"]["max_value"] == 30_000_000


def test_graph_short_role_plus_location_is_job_search():
    graph = build_recruitment_graph()
    result = graph.invoke({"session_id": "s5", "user_query": "AI Engineer tai HCM", "entities": {}})
    assert result["intent"] == "job_search"
    assert "AI Engineer" in result["entities"]["position"]
    assert "Ho Chi Minh City" in result["entities"]["location"]


def test_graph_supports_non_it_roles():
    graph = build_recruitment_graph()
    result = graph.invoke({"session_id": "s6", "user_query": "Tim viec ke toan tai Ha Noi", "entities": {}})
    assert result["intent"] == "job_search"
    assert any("ke toan" in item.lower() for item in result["entities"]["position"])
    assert "Hanoi" in result["entities"]["location"]


def test_graph_data_analytics_without_job_keyword():
    graph = build_recruitment_graph()
    result = graph.invoke({"session_id": "s7", "user_query": "Data Analytics o Viet Nam", "entities": {}})
    assert result["intent"] == "job_search"
    assert any("data analytics" in item.lower() for item in result["entities"]["position"])
    assert "Vietnam" in result["entities"]["location"]


def test_graph_data_analytics_job_phrase_extracts_role_not_location():
    graph = build_recruitment_graph()
    result = graph.invoke({"session_id": "s8", "user_query": "Data Analytics job o Ha Noi", "entities": {}})
    assert result["intent"] == "job_search"
    assert any("data analytics" in item.lower() for item in result["entities"]["position"])
    assert "Hanoi" in result["entities"]["location"]


def test_graph_supports_additional_non_it_industries():
    graph = build_recruitment_graph()
    result = graph.invoke({"session_id": "s9", "user_query": "Tim viec phap che tai Ha Noi", "entities": {}})
    assert result["intent"] == "job_search"
    assert any("legal counsel" in item.lower() for item in result["entities"]["position"])
    assert "Hanoi" in result["entities"]["location"]


def test_graph_extracts_experience_years():
    graph = build_recruitment_graph()
    result = graph.invoke(
        {"session_id": "s10", "user_query": "Tim viec AI Engineer kinh nghiem 1 nam tai Ha Noi", "entities": {}}
    )
    assert result["intent"] == "job_search"
    assert result["entities"]["experience_years"] == 1


def test_graph_follow_up_keeps_previous_position_memory():
    graph = build_recruitment_graph()
    first = graph.invoke({"session_id": "s11", "user_query": "Tim viec AI Engineer", "entities": {}})
    second = graph.invoke(
        {
            "session_id": "s11",
            "user_query": "o Ha Noi",
            "entities": first.get("entities", {}),
        }
    )
    assert second["intent"] == "job_search"
    assert any("ai engineer" in item.lower() for item in second["entities"]["position"])
    assert "Hanoi" in second["entities"]["location"]


def test_build_job_list_response_includes_company_when_available():
    text = _build_job_list_response(
        "vi",
        [
            {
                "title": "AI Engineer",
                "company": "ABC Tech",
                "location": "Ho Chi Minh City",
                "salary_min": 20_000_000,
                "salary_max": 30_000_000,
                "experience": "2-4 nam",
            }
        ],
    )
    assert "ABC Tech" in text
    assert "AI Engineer" in text
    assert "Kinh nghiem: 2-4 nam" in text


def test_build_job_list_response_no_experience_match_suffix():
    text = _build_job_list_response(
        "vi",
        [
            {
                "title": "AI Engineer",
                "company_name": "ABC Tech",
                "location": "Hanoi",
                "salary_min": 15_000_000,
                "salary_max": 20_000_000,
                "experience": "0-1 nam",
            }
        ],
        target_experience_years=1,
    )
    assert "Khop yeu cau 1 nam" not in text
