"""서버 기동 스모크 테스트."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok():
    # When the health endpoint is called
    resp = client.get("/health")

    # Then the server is up and reports ok
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
