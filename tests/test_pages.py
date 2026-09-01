"""The health probe and the two HTML surfaces stay reachable."""


def test_health_touches_nothing_downstream(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_landing_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_review_page_is_served(client):
    response = client.get("/review/anything")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
