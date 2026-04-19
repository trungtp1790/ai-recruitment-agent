from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_redirects_to_chatbot():
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code in {302, 307}
    assert response.headers["location"] == "/chatbot"


def test_chatbot_ui_page():
    client = TestClient(app)
    response = client.get("/chatbot")
    assert response.status_code == 200
    assert "AI Recruitment Agent" in response.text


def test_chat_endpoint():
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"session_id": "api-s1", "message": "Tim viec AI Engineer luong 20-30 trieu"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["intent"] == "job_search"
    assert payload["state"]["salary"]["min_value"] == 20_000_000


def test_chat_endpoint_supports_get():
    client = TestClient(app)
    response = client.get(
        "/api/chat",
        params={"session_id": "api-s2", "message": "Tim viec Data Scientist luong 25-35 trieu"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["intent"] == "job_search"
    assert payload["state"]["salary"]["min_value"] == 25_000_000
