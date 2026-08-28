import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"CampusPulse AI" in response.data


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "healthy"


def test_analyze_api(client):
    response = client.post("/api/analyze", json={"text": "The laboratory was excellent and helpful"})
    assert response.status_code == 200
    assert set(response.json) == {
        "confidence", "keywords", "priority", "probabilities", "recommendation", "sentiment"
    }


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        ({"data": "plain text"}, 415),
        ({"json": {}}, 400),
        ({"json": {"text": ""}}, 400),
        ({"json": {"text": "x" * 2001}}, 400),
    ],
)
def test_invalid_requests(client, kwargs, status):
    assert client.post("/api/analyze", **kwargs).status_code == status

