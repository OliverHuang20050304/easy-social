from __future__ import annotations

import re

import pytest
from flask import session

from easy_social.captcha import (
    SESSION_CHALLENGE_KEY,
    CaptchaStore,
    clear_challenge,
    generate_challenge,
    get_store,
    verify_response,
)

pytestmark = pytest.mark.unit


def test_generate_challenge_stores_token_in_session_and_answer_in_store(app):
    with app.test_request_context():
        question = generate_challenge(session)

        assert re.fullmatch(r"\d+ \+ \d+ = \?", question)
        assert SESSION_CHALLENGE_KEY in session
        assert "captcha_answer" not in session

        challenge_id = session[SESSION_CHALLENGE_KEY]
        left, right = map(int, question.replace(" = ?", "").split(" + "))
        assert get_store().pop(challenge_id) == left + right


def test_verify_response_accepts_correct_answer(app):
    store = CaptchaStore()
    challenge_id = store.create(8)

    with app.test_request_context() as ctx:
        ctx.session[SESSION_CHALLENGE_KEY] = challenge_id
        app.config["CAPTCHA_STORE"] = store

        assert verify_response(session, "8") is True
        assert SESSION_CHALLENGE_KEY not in session
        assert challenge_id not in store._answers


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ("9", False),
        ("", False),
        ("abc", False),
    ],
)
def test_verify_response_rejects_invalid_answers(app, response: str, expected: bool):
    store = CaptchaStore()
    challenge_id = store.create(8)

    with app.test_request_context() as ctx:
        ctx.session[SESSION_CHALLENGE_KEY] = challenge_id
        app.config["CAPTCHA_STORE"] = store

        assert verify_response(session, response) is expected
        assert SESSION_CHALLENGE_KEY not in session
        assert challenge_id not in store._answers


def test_verify_response_without_session_token_fails(app):
    with app.test_request_context():
        assert verify_response(session, "8") is False


def test_clear_challenge_removes_token_and_store_entry(app):
    store = CaptchaStore()
    challenge_id = store.create(8)

    with app.test_request_context() as ctx:
        ctx.session[SESSION_CHALLENGE_KEY] = challenge_id
        app.config["CAPTCHA_STORE"] = store

        clear_challenge(session)

        assert SESSION_CHALLENGE_KEY not in session
        assert challenge_id not in store._answers
