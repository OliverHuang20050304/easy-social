from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from easy_social import create_app
from easy_social.captcha import SESSION_CHALLENGE_KEY
from easy_social.extensions import db

CAPTCHA_QUESTION_RE = re.compile(
    rb'<span class="captcha-question">(\d+) \+ (\d+) = \?</span>'
)


@pytest.fixture()
def app():
    with tempfile.TemporaryDirectory() as temp_dir:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "UPLOAD_FOLDER": str(Path(temp_dir) / "uploads"),
                "MEDIA_STORAGE_BACKEND": "local",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with app.app_context():
            db.create_all()
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def captcha_answer_for_session(client) -> str:
    response = client.get("/auth/register")
    with client.session_transaction() as flask_session:
        if "captcha_answer" in flask_session:
            raise RuntimeError("CAPTCHA answer must not be stored in the Flask session.")
        if SESSION_CHALLENGE_KEY not in flask_session:
            raise RuntimeError("CAPTCHA challenge id was not stored in the session.")

    match = CAPTCHA_QUESTION_RE.search(response.data)
    if not match:
        raise RuntimeError("CAPTCHA question was not found on the register page.")

    left, right = int(match.group(1)), int(match.group(2))
    return str(left + right)


def register(
    client,
    username: str,
    email: str | None = None,
    password: str = "password",
    *,
    captcha_answer: str | None = None,
):
    data = {
        "username": username,
        "email": email or f"{username}@example.com",
        "password": password,
        "captcha_answer": (
            captcha_answer
            if captcha_answer is not None
            else captcha_answer_for_session(client)
        ),
    }
    return client.post("/auth/register", data=data, follow_redirects=True)


def login(client, username_or_email: str, password: str = "password"):
    return client.post(
        "/auth/login",
        data={"username_or_email": username_or_email, "password": password},
        follow_redirects=True,
    )


def logout(client):
    return client.post("/auth/logout", follow_redirects=True)
