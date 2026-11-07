import io

from PIL import Image

from app import models
from app.database import SessionLocal
from tests.conftest import image_bytes, login, register


# ---------- registration ----------

def test_register_returns_profile_without_password(client):
    user = register(client, "Alice")
    assert user["username"] == "Alice"
    assert user["email"] == "alice@example.com"
    assert "password" not in user
    assert user["image_url"] == "/static/img/default-avatar.svg"


def test_register_stores_hashed_password(client):
    register(client, "alice", password="password123")
    with SessionLocal() as db:
        stored = db.query(models.Users).one().password
    assert stored != "password123" and stored.startswith("$2")


def test_duplicate_email_is_409_not_500(client):
    register(client, "alice", email="a@example.com")
    r = client.post("/users/", json={"email": "A@Example.com", "username": "other", "password": "password123"})
    assert r.status_code == 409


def test_duplicate_username_ignores_case(client):
    register(client, "alice")
    r = client.post("/users/", json={"email": "new@example.com", "username": "ALICE", "password": "password123"})
    assert r.status_code == 409


def test_short_password_rejected(client):
    r = client.post("/users/", json={"email": "a@example.com", "username": "alice", "password": "short"})
    assert r.status_code == 422


def test_password_over_72_bytes_rejected(client):
    r = client.post("/users/", json={"email": "a@example.com", "username": "alice", "password": "x" * 73})
    assert r.status_code == 422


def test_bad_username_rejected(client):
    for bad in ("ab", "has space", "semi;colon", "x" * 31):
        r = client.post("/users/", json={"email": "a@example.com", "username": bad, "password": "password123"})
        assert r.status_code == 422, bad


# ---------- login ----------

def test_login_with_email_or_username_any_case(client):
    register(client, "alice")
    assert "Authorization" in login(client, "alice@example.com")
    assert "Authorization" in login(client, "ALICE")
    assert "Authorization" in login(client, "Alice@Example.com")


def test_wrong_password_and_unknown_user_look_identical(client):
    register(client, "alice")
    wrong = client.post("/login", data={"username": "alice", "password": "nope-nope"})
    unknown = client.post("/login", data={"username": "ghost", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_protected_routes_need_a_token(client):
    assert client.get("/posts/").status_code == 401
    assert client.get("/users/me").status_code == 401
    assert client.get("/posts/", headers={"Authorization": "Bearer garbage"}).status_code == 401


# ---------- profile ----------

def test_me_and_public_profile_hide_email_from_others(client, alice, bob):
    _, alice_h = alice
    _, bob_h = bob
    assert client.get("/users/me", headers=alice_h).json()["email"] == "alice@example.com"
    public = client.get("/users/alice", headers=bob_h)
    assert public.status_code == 200
    assert "email" not in public.json()
    assert public.json()["posts_count"] == 0
    assert client.get("/users/nobody", headers=bob_h).status_code == 404


def test_update_profile_and_username_conflict(client, alice, bob):
    _, alice_h = alice
    r = client.patch("/users/me", json={"bio": "Hello there", "username": "alice_2"}, headers=alice_h)
    assert r.status_code == 200 and r.json()["bio"] == "Hello there" and r.json()["username"] == "alice_2"
    r = client.patch("/users/me", json={"username": "BOB"}, headers=alice_h)
    assert r.status_code == 409


def test_change_password(client, alice):
    _, h = alice
    bad = client.post("/users/me/password", json={"current_password": "wrongwrong", "new_password": "brandnew123"}, headers=h)
    assert bad.status_code == 400
    ok = client.post("/users/me/password", json={"current_password": "password123", "new_password": "brandnew123"}, headers=h)
    assert ok.status_code == 200
    assert client.post("/login", data={"username": "alice", "password": "password123"}).status_code == 401
    assert client.post("/login", data={"username": "alice", "password": "brandnew123"}).status_code == 200


# ---------- profile picture ----------

def test_upload_valid_picture_is_resized_square_jpeg(client, alice):
    _, h = alice
    r = client.post("/users/me/picture", headers=h,
                    files={"file": ("big.png", image_bytes("PNG", (1200, 600)), "image/png")})
    assert r.status_code == 200
    url = r.json()["image_url"]
    assert url.startswith("/media/profile_pics/") and url.endswith(".jpg")
    served = client.get(url)
    assert served.status_code == 200
    img = Image.open(io.BytesIO(served.content))
    assert img.size == (400, 400) and img.format == "JPEG"


def test_png_with_transparency_is_accepted(client, alice):
    _, h = alice
    r = client.post("/users/me/picture", headers=h,
                    files={"file": ("t.png", image_bytes("PNG", (50, 50), "RGBA", (0, 0, 0, 0)), "image/png")})
    assert r.status_code == 200


def test_text_file_pretending_to_be_png_is_rejected(client, alice):
    _, h = alice
    r = client.post("/users/me/picture", headers=h,
                    files={"file": ("evil.png", b"<script>alert(1)</script>", "image/png")})
    assert r.status_code == 400


def test_unsupported_image_format_rejected(client, alice):
    _, h = alice
    r = client.post("/users/me/picture", headers=h,
                    files={"file": ("a.gif", image_bytes("GIF", (20, 20), "P", 0), "image/gif")})
    assert r.status_code == 400


def test_oversized_upload_rejected(client, alice, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    _, h = alice
    r = client.post("/users/me/picture", headers=h,
                    files={"file": ("big.bin", b"0" * (1024 * 1024 + 10), "image/png")})
    assert r.status_code == 413


def test_replacing_and_removing_picture_deletes_old_file(client, alice):
    from app import storage
    _, h = alice
    first = client.post("/users/me/picture", headers=h, files={"file": ("a.png", image_bytes(), "image/png")}).json()["image_url"]
    second = client.post("/users/me/picture", headers=h, files={"file": ("b.png", image_bytes(color=(0, 0, 200)), "image/png")}).json()["image_url"]
    assert first != second
    assert client.get(first).status_code == 404
    assert client.get(second).status_code == 200
    removed = client.delete("/users/me/picture", headers=h).json()
    assert removed["image_url"] == "/static/img/default-avatar.svg"
    assert client.get(second).status_code == 404


def test_picture_upload_requires_login(client):
    r = client.post("/users/me/picture", files={"file": ("a.png", image_bytes(), "image/png")})
    assert r.status_code == 401
