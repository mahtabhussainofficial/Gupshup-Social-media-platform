"""Test setup.

Tests run against a REAL PostgreSQL database, but never your development one:
the database name gets a "_test" suffix and is created automatically if missing.
(Postgres-specific features such as now() and lower() indexes would not behave the
same on SQLite, so SQLite would give false confidence.)
"""
import io
import os
import tempfile
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parent.parent


def _test_database_url() -> str:
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    return URL.create(
        "postgresql+psycopg",
        username=env.get("DATABASE_USERNAME", "postgres"),
        password=env.get("DATABASE_PASSWORD", ""),
        host=env.get("DATABASE_HOSTNAME", "localhost"),
        port=int(env.get("DATABASE_PORT", 5432)),
        database=f"{env.get('DATABASE_NAME', 'app')}_test",
    ).render_as_string(hide_password=False)


def _create_database_if_missing(url_str: str) -> None:
    import psycopg
    url = make_url(url_str)
    with psycopg.connect(
        host=url.host, port=url.port, user=url.username, password=url.password,
        dbname="postgres", autocommit=True,
    ) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{url.database}"')


TEST_DB_URL = _test_database_url()
_create_database_if_missing(TEST_DB_URL)

# These must be set BEFORE the app is imported, because the app reads them at import time.
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-anywhere-else")
os.environ["EMAIL_BACKEND"] = "console"
os.environ["MEDIA_DIR"] = tempfile.mkdtemp(prefix="gupshup_test_media_")

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Every test starts with empty tables."""
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users, posts, votes, comments, password_reset_tokens RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def register(client, username="alice", email=None, password="password123"):
    email = email or f"{username}@example.com"
    r = client.post("/users/", json={"email": email, "username": username, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def login(client, identifier, password="password123"):
    r = client.post("/login", data={"username": identifier, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def make_user(client):
    """make_user("bob") -> (user_json, auth_headers)"""
    def _make(username="alice", password="password123"):
        user = register(client, username, password=password)
        return user, login(client, username, password)
    return _make


@pytest.fixture
def alice(make_user):
    return make_user("alice")


@pytest.fixture
def bob(make_user):
    return make_user("bob")


def image_bytes(fmt="PNG", size=(800, 600), mode="RGB", color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format=fmt)
    return buf.getvalue()
