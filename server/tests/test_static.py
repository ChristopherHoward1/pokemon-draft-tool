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


def test_missing_sprites_return_json_404(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "SPRITES_DIR", tmp_path / "missing")

    with TestClient(main.app, raise_server_exceptions=False) as client:
        for path in ("/sprites/pikachu.png", "/sprites/", "/sprites/%00"):
            response = client.get(path)
            assert response.status_code == 404
            assert response.headers["content-type"].startswith("application/json")
            assert response.json() == {"reason": "Not found"}


def test_sprite_file_and_traversal(tmp_path, monkeypatch):
    sprites = tmp_path / "sprites"
    sprites.mkdir()
    (sprites / "a.png").write_bytes(b"image bytes")
    (tmp_path / "secret").write_text("private")
    monkeypatch.setattr(main, "SPRITES_DIR", sprites)

    with TestClient(main.app) as client:
        response = client.get("/sprites/a.png")
        assert response.status_code == 200
        assert response.content == b"image bytes"

        response = client.get("/sprites/..%2Fsecret")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"reason": "Not found"}
        assert response.text != "private"


def test_nul_paths_return_json_404(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "CLIENT_DIST", tmp_path)

    with TestClient(main.app, raise_server_exceptions=False) as client:
        for path in ("/%00", "/lobby/%00"):
            response = client.get(path)
            assert response.status_code == 404
            assert response.headers["content-type"].startswith("application/json")
            assert response.json() == {"reason": "Not found"}


def test_overlong_path_segments_do_not_500(tmp_path, monkeypatch):
    sprites = tmp_path / "sprites"
    sprites.mkdir()
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>draft</html>")
    monkeypatch.setattr(main, "SPRITES_DIR", sprites)
    monkeypatch.setattr(main, "CLIENT_DIST", dist)
    long_name = "a" * 5000

    with TestClient(main.app, raise_server_exceptions=False) as client:
        response = client.get(f"/sprites/{long_name}")
        assert response.status_code == 404
        assert response.json() == {"reason": "Not found"}

        response = client.get(f"/{long_name}")
        assert response.status_code == 200
        assert response.text == "<html>draft</html>"


def test_head_sprite_matches_get_length(tmp_path, monkeypatch):
    (tmp_path / "a.png").write_bytes(b"image bytes")
    monkeypatch.setattr(main, "SPRITES_DIR", tmp_path)

    with TestClient(main.app) as client:
        get_response = client.get("/sprites/a.png")
        head_response = client.head("/sprites/a.png")
        assert head_response.status_code == 200
        assert head_response.content == b""
        assert head_response.headers["content-length"] == get_response.headers["content-length"]
        assert client.head("/sprites/missing.png").status_code == 404


def test_head_client_and_health(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>draft</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log('draft')")
    monkeypatch.setattr(main, "CLIENT_DIST", tmp_path)

    with TestClient(main.app) as client:
        for path in ("/", "/assets/app.js"):
            response = client.head(path)
            assert response.status_code == 200
            assert response.content == b""
        assert client.head("/health").status_code == 200
        assert client.head("/session/X").status_code == 404
