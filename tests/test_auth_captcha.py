from __future__ import annotations

import pytest

from easy_social.extensions import db
from easy_social.models import User

from conftest import captcha_answer_for_session, register

pytestmark = pytest.mark.integration


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
