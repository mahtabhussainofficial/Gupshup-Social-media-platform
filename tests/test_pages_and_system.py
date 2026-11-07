import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from app.database import Base
from tests.conftest import ROOT, TEST_DB_URL


@pytest.mark.parametrize("path", ["/", "/login", "/register", "/forgot-password",
                                  "/reset-password?token=abc", "/account", "/post/1", "/u/alice"])
def test_pages_render(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert '<script src="/static/js/app.js"' in r.text


def test_profile_page_escapes_username(client):
    r = client.get("/u/%3Cimg%20src=x%20onerror=alert(1)%3E")
    assert r.status_code == 200
    assert "<img src=x" not in r.text
    assert "&lt;img src=x" in r.text


def test_static_assets_are_served(client):
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/static/img/default-avatar.svg").status_code == 200


def test_security_headers_and_docs_exemption(client):
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert "x-process-time-ms" in r.headers
    assert "content-security-policy" not in client.get("/docs").headers  # Swagger UI needs its CDN


def test_health_checks_database(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "database": "ok"}


def test_migrations_build_the_same_schema_as_the_models():
    """Runs `alembic upgrade head` on a throwaway database, then asks Alembic whether the
    result differs from models.py. Catches 'I changed a model but forgot the migration'."""
    import psycopg
    from sqlalchemy.engine import make_url
    url = make_url(TEST_DB_URL)
    scratch = f"{url.database}_migrations"
    with psycopg.connect(host=url.host, port=url.port, user=url.username, password=url.password,
                         dbname="postgres", autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{scratch}"')
        conn.execute(f'CREATE DATABASE "{scratch}"')
    scratch_url = url.set(database=scratch).render_as_string(hide_password=False)

    import os
    old = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = scratch_url
    try:
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "alembic"))
        command.upgrade(cfg, "head")
        eng = create_engine(scratch_url)
        with eng.connect() as conn:
            diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        eng.dispose()
        assert diffs == [], diffs
        # downgrade all the way and back up, to prove downgrades work too
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
    finally:
        os.environ["DATABASE_URL"] = old
