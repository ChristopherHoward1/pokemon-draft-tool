"""Single-origin client serving and API fallbacks."""

from fastapi.testclient import TestClient

from server import main


def test_client_files_and_fallbacks(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>draft</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log('draft')")
    monkeypatch.setattr(main, "CLIENT_DIST", tmp_path)

    with TestClient(main.app) as client:
        for path in ("/", "/lobby/ABCD"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html")
            assert response.text == "<html>draft</html>"

        assert client.get("/assets/app.js").text == "console.log('draft')"
        assert client.get("/health").json() == {"status": "ok"}

        for path in ("/session/NOPE/bogus", "/health/x", "/sprites"):
            response = client.get(path, follow_redirects=True)
            assert response.status_code == 404
            assert response.headers["content-type"].startswith("application/json")
            assert response.json() == {"reason": "Not found"}


def test_traversal_and_missing_build(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (tmp_path / "secret").write_text("private")
    monkeypatch.setattr(main, "CLIENT_DIST", dist)

    with TestClient(main.app) as client:
        response = client.get("/assets/..%2F..%2Fsecret")
        assert response.status_code == 404
        assert response.text != "private"
        response = client.get("/lobby/ABCD")
        assert response.status_code == 404
        assert response.json() == {
            "reason": "Client not built — run npm --prefix client run build"
        }

    (dist / "index.html").symlink_to(tmp_path / "secret")
    with TestClient(main.app) as client:
        response = client.get("/lobby/ABCD")
        assert response.status_code == 404
        assert response.text != "private"
