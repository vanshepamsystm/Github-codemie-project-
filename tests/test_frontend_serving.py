from fastapi.testclient import TestClient


def test_home_serves_index_html(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<html" in resp.text.lower()


def test_static_assets_are_served(client: TestClient):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_missing_static_asset_returns_404(client: TestClient):
    assert client.get("/static/does-not-exist.js").status_code == 404
