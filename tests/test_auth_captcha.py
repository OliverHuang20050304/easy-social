from __future__ import annotations

from datetime import timedelta

import pytest

from easy_social.captcha import SESSION_CHALLENGE_KEY
from easy_social.extensions import db
from easy_social.models import CaptchaChallenge, User, _utc_now_naive

from conftest import captcha_answer_for_session, register

pytestmark = pytest.mark.integration


def test_captcha_answer_not_stored_in_flask_session(client, app):
    client.get("/auth/register")

    with client.session_transaction() as flask_session:
        assert "captcha_answer" not in flask_session
        challenge_id = flask_session.get(SESSION_CHALLENGE_KEY)

    assert challenge_id
    with app.app_context():
        challenge = db.session.get(CaptchaChallenge, challenge_id)
        assert challenge is not None
        assert not challenge.is_expired


def test_register_page_shows_captcha_question(client):
    response = client.get("/auth/register")

    assert response.status_code == 200
    assert b"Security check:" in response.data
    assert b"class=\"captcha-question\"" in response.data


def test_register_succeeds_with_valid_captcha(client, app):
    response = register(client, "alice")

    assert response.status_code == 200
    assert b"Feed" in response.data
    with app.app_context():
        assert User.query.filter_by(username="alice").one()


def test_register_fails_when_captcha_missing(client, app):
    client.get("/auth/register")
    response = client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password",
            "captcha_answer": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Please complete the CAPTCHA." in response.data
    with app.app_context():
        assert User.query.filter_by(username="alice").count() == 0


def test_register_fails_when_captcha_incorrect(client, app):
    client.get("/auth/register")
    response = client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password",
            "captcha_answer": "99999",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"CAPTCHA answer is incorrect. Please try again." in response.data
    with app.app_context():
        assert User.query.filter_by(username="alice").count() == 0


def test_register_fails_when_captcha_expired(client, app):
    client.get("/auth/register")
    with client.session_transaction() as flask_session:
        challenge_id = flask_session[SESSION_CHALLENGE_KEY]

    with app.app_context():
        challenge = db.session.get(CaptchaChallenge, challenge_id)
        challenge.expires_at = _utc_now_naive() - timedelta(seconds=1)
        db.session.commit()
        answer = str(challenge.answer)

    response = client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password",
            "captcha_answer": answer,
        },
        follow_redirects=True,
    )

    assert b"CAPTCHA answer is incorrect. Please try again." in response.data
    with app.app_context():
        assert User.query.filter_by(username="alice").count() == 0
        assert db.session.get(CaptchaChallenge, challenge_id) is None


def test_register_consumes_challenge_so_it_cannot_be_reused(client, app):
    answer = captcha_answer_for_session(client)
    with client.session_transaction() as flask_session:
        challenge_id = flask_session[SESSION_CHALLENGE_KEY]

    first = client.post(
        "/auth/register",
        data={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password",
            "captcha_answer": answer,
        },
        follow_redirects=True,
    )
    assert b"Feed" in first.data

    client.post("/auth/logout", follow_redirects=True)

    second = client.post(
        "/auth/register",
        data={
            "username": "bob",
            "email": "bob@example.com",
            "password": "password",
            "captcha_answer": answer,
        },
        follow_redirects=True,
    )

    assert b"CAPTCHA answer is incorrect. Please try again." in second.data
    with app.app_context():
        assert db.session.get(CaptchaChallenge, challenge_id) is None
        assert User.query.filter_by(username="bob").count() == 0


def test_register_fails_with_wrong_captcha_even_when_fields_are_valid(client, app):
    answer = captcha_answer_for_session(client)
    wrong_answer = "0" if answer != "0" else "1"
    response = client.post(
        "/auth/register",
        data={
            "username": "validuser",
            "email": "validuser@example.com",
            "password": "password",
            "captcha_answer": wrong_answer,
        },
        follow_redirects=True,
    )

    assert b"CAPTCHA answer is incorrect. Please try again." in response.data
    with app.app_context():
        assert User.query.filter_by(username="validuser").count() == 0
