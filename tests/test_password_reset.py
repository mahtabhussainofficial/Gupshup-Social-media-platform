import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import text

from app import mailer
from app.database import engine
from tests.conftest import register


def request_reset(client, email, sent):
    """Calls /forgot-password with the email sender replaced by a recorder (a mock)."""
    with patch.object(mailer, "send_email", side_effect=lambda to, subj, body: sent.append((to, subj, body))):
        return client.post("/forgot-password", json={"email": email})


def token_from(sent):
    return re.search(r"token=([\w\-]+)", sent[-1][2]).group(1)


def test_full_reset_flow(client):
    register(client, "alice", password="oldpassword1")
    sent = []
    r = request_reset(client, "alice@example.com", sent)
    assert r.status_code == 202
    assert len(sent) == 1 and sent[0][0] == "alice@example.com"

    token = token_from(sent)
    ok = client.post("/reset-password", json={"token": token, "new_password": "newpassword1"})
    assert ok.status_code == 200
    assert client.post("/login", data={"username": "alice", "password": "oldpassword1"}).status_code == 401
    assert client.post("/login", data={"username": "alice", "password": "newpassword1"}).status_code == 200

    # The link works only once.
    again = client.post("/reset-password", json={"token": token, "new_password": "another-pass1"})
    assert again.status_code == 400


def test_response_is_identical_for_unknown_email_and_sends_nothing(client):
    register(client, "alice")
    sent = []
    known = request_reset(client, "alice@example.com", sent)
    unknown = request_reset(client, "ghost@example.com", sent)
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(sent) == 1  # only the real account got an email


def test_only_a_hash_of_the_token_is_stored(client):
    register(client, "alice")
    sent = []
    request_reset(client, "alice@example.com", sent)
    token = token_from(sent)
    with engine.connect() as conn:
        stored = conn.execute(text("select token_hash from password_reset_tokens")).scalar()
    assert stored != token and token not in stored and len(stored) == 64


def test_newer_link_replaces_older_one(client):
    register(client, "alice")
    sent = []
    request_reset(client, "alice@example.com", sent)
    first = token_from(sent)
    request_reset(client, "alice@example.com", sent)
    second = token_from(sent)
    assert first != second
    assert client.post("/reset-password", json={"token": first, "new_password": "newpassword1"}).status_code == 400
    assert client.post("/reset-password", json={"token": second, "new_password": "newpassword1"}).status_code == 200


def test_expired_token_is_rejected(client):
    register(client, "alice")
    sent = []
    request_reset(client, "alice@example.com", sent)
    token = token_from(sent)
    with engine.begin() as conn:
        conn.execute(text("update password_reset_tokens set expires_at = :t"),
                     {"t": datetime.now(timezone.utc) - timedelta(minutes=1)})
    r = client.post("/reset-password", json={"token": token, "new_password": "newpassword1"})
    assert r.status_code == 400


def test_garbage_token_and_weak_new_password(client):
    register(client, "alice")
    assert client.post("/reset-password", json={"token": "x" * 40, "new_password": "newpassword1"}).status_code == 400
    sent = []
    request_reset(client, "alice@example.com", sent)
    r = client.post("/reset-password", json={"token": token_from(sent), "new_password": "short"})
    assert r.status_code == 422


def test_reset_link_uses_configured_base_url_and_expiry_is_30_minutes(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "app_base_url", "https://myapp.example.com/")
    register(client, "alice")
    sent = []
    request_reset(client, "alice@example.com", sent)
    assert "https://myapp.example.com/reset-password?token=" in sent[0][2]
    with engine.connect() as conn:
        expires = conn.execute(text("select expires_at from password_reset_tokens")).scalar()
    minutes = (expires - datetime.now(timezone.utc)).total_seconds() / 60
    assert 29 < minutes <= 30


# ---------- the mailer itself ----------

def test_smtp_backend_sends_through_smtp_server(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "user")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    fake_smtp = MagicMock()
    with patch("app.mailer.smtplib.SMTP") as smtp_class:
        smtp_class.return_value.__enter__.return_value = fake_smtp
        mailer.send_email("to@example.com", "Subject", "Body")
    smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=10)
    fake_smtp.starttls.assert_called_once()
    fake_smtp.login.assert_called_once_with("user", "secret")
    sent_message = fake_smtp.send_message.call_args[0][0]
    assert sent_message["To"] == "to@example.com" and sent_message["Subject"] == "Subject"


def test_email_failure_in_background_task_does_not_crash(monkeypatch, caplog):
    with patch.object(mailer, "send_email", side_effect=ConnectionError("smtp down")):
        mailer.send_password_reset_email("a@example.com", "http://x/reset?token=abc")  # must not raise
    assert "Could not send password reset email" in caplog.text
